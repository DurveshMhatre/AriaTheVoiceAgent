from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    Agent,
    AgentSession,
    APIConnectOptions,
    ChatContext,
    ChatMessage,
    ModelSettings,
    NotGivenOr,
    TurnHandlingOptions,
    llm,
    room_io,
)
from livekit.agents.voice.agent_session import SessionConnectOptions
from livekit.plugins import sarvam

from brain.clock import SystemClock
from brain.config import TenantConfigLoader
from brain.events import event as make_event
from brain.repo import InMemoryOrderRepository
from brain.state import CallState
from brain.summary import deterministic_summary
from brain.tools import ToolDispatcher
from brain.turn import Brain, UserTurn
from providers.llm.factory import create_llm, create_real_llm
from voice.usage import SupabaseUsageMeter

from .settings import VoiceSettings

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("aria.voice")


class _BrainLlm(llm.LLM[Any]):
    """SDK capability marker only: the overridden node owns all Brain inference."""

    def chat(
        self,
        *,
        chat_ctx: ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> llm.LLMStream:
        raise RuntimeError("BrainAgent.llm_node must handle inference through the Brain")


class _SessionCloser:
    """Request synchronously; never await close from a node it will cancel."""

    def __init__(self, session: Any) -> None:
        self.session = session
        self.task: asyncio.Task[None] | None = None

    def request(self) -> None:
        if self.task is None:
            self.task = asyncio.create_task(self.session.aclose())

    async def wait(self) -> None:
        self.request()
        assert self.task is not None
        await asyncio.shield(self.task)


class BrainAgent(Agent):
    def __init__(
        self,
        brain: Brain,
        publish_event: Any,
        *,
        max_call_seconds: int,
        max_tts_characters: int,
        call_started_at: float,
    ) -> None:
        super().__init__(
            instructions="Route every turn through the Aura policy Brain.", llm=_BrainLlm()
        )
        self.brain = brain
        self.publish_event = publish_event
        self.max_call_seconds = max_call_seconds
        self.max_tts_characters = max_tts_characters
        self.tts_characters = 0
        self.call_started_at = call_started_at
        self._interrupted = False
        self.fallback_requested = False
        self.fallback_kind = "stt"
        self.fallback_provider = "sarvam_voice"
        self.shutdown_session: Any = None

    def request_fallback(self, kind: str, provider: str) -> None:
        if self.fallback_requested:
            return
        self.fallback_requested = True
        self.fallback_kind = kind
        self.fallback_provider = provider
        if self.shutdown_session is not None:
            self.shutdown_session()

    async def llm_node(
        self,
        chat_ctx: ChatContext,
        tools: list[llm.Tool],
        model_settings: ModelSettings,
    ) -> AsyncIterable[llm.ChatChunk | str | Any]:
        if time.monotonic() - self.call_started_at >= self.max_call_seconds:
            await self.publish_event(
                "error",
                {
                    "code": "CALL_DURATION_LIMIT",
                    "message": "This demo call has reached its five-minute limit.",
                },
            )
            if self.shutdown_session is not None:
                self.shutdown_session()
            return

        user_text = _latest_user_text(chat_ctx)
        if not user_text:
            sentence = "I didn't catch that, could you repeat?"
            if self._within_tts_cap(sentence):
                yield sentence
            else:
                await self._signal_tts_cap()
            return

        try:
            async for brain_event in self.brain.handle_turn(UserTurn(user_text)):
                if brain_event.kind == "FILLER":
                    sentence = str(brain_event.payload.get("text", ""))
                    if not self._within_tts_cap(sentence):
                        await self._signal_tts_cap()
                        return
                    yield sentence
                elif brain_event.kind == "SENTENCE":
                    sentence = str(brain_event.payload.get("text", ""))
                    if not self._within_tts_cap(sentence):
                        await self._signal_tts_cap()
                        return
                    yield sentence
                elif brain_event.kind == "TOOL_CALL":
                    tool_id = str(brain_event.payload.get("call_id") or "tool")
                    await self.publish_event(
                        "tool_called",
                        {
                            "tool_name": str(brain_event.payload.get("name", "unknown")),
                            "arguments": brain_event.payload.get("arguments") or {},
                        },
                        turn_id=f"turn-{self.brain.state.turn_count}",
                    )
                    logger.info(
                        json.dumps(
                            {
                                "event": "tool_called",
                                "call_id": self.publish_event.call_id,
                                "turn_id": f"turn-{self.brain.state.turn_count}",
                                "tenant_id": self.publish_event.tenant_id,
                                "tool_call_id": tool_id,
                            }
                        )
                    )
                elif brain_event.kind == "TOOL_RESULT":
                    result = brain_event.payload.get("result", {})
                    await self.publish_event(
                        "tool_result",
                        {
                            "tool_name": str(brain_event.payload.get("name", "unknown")),
                            "ok": bool(result.get("ok")) if isinstance(result, dict) else False,
                            "error_code": (
                                result.get("error_code") if isinstance(result, dict) else None
                            ),
                            "speakable_hint": (
                                result.get("speakable_hint") if isinstance(result, dict) else None
                            ),
                        },
                        turn_id=f"turn-{self.brain.state.turn_count}",
                    )
                elif brain_event.kind == "DONE":
                    if brain_event.payload.get("guardrail_triggered"):
                        await self.publish_event(
                            "guardrail_triggered",
                            {"rule": "output_validator"},
                            turn_id=f"turn-{self.brain.state.turn_count}",
                        )
        except asyncio.CancelledError:
            self._interrupted = True
            raise
        except Exception as exc:
            logger.error(
                json.dumps(
                    {
                        "event": "llm_failure",
                        "error_type": type(exc).__name__,
                        "call_id": self.publish_event.call_id,
                        "turn_id": f"turn-{self.brain.state.turn_count}",
                        "tenant_id": self.publish_event.tenant_id,
                    }
                )
            )
            self.request_fallback("llm", "configured_llm")
            return

    def _within_tts_cap(self, sentence: str) -> bool:
        if self.tts_characters + len(sentence) > self.max_tts_characters:
            return False
        self.tts_characters += len(sentence)
        return True

    async def _signal_tts_cap(self) -> None:
        await self.publish_event(
            "error",
            {
                "code": "PER_CALL_TTS_LIMIT",
                "message": "Voice capacity for this call is used.",
            },
        )
        self.request_fallback("tts", "sarvam_tts")


class EventPublisher:
    def __init__(self, room: Any, call_id: str, tenant_id: str) -> None:
        self.room = room
        self.call_id = call_id
        self.tenant_id = tenant_id
        self.sequence = 0
        self.transcript: list[dict[str, Any]] = []
        self.summary_state = CallState()
        self.pending_events: set[asyncio.Task[None]] = set()

    def schedule(
        self,
        event_type: str,
        data: dict[str, Any],
        *,
        turn_id: str | None = None,
    ) -> None:
        task = asyncio.create_task(self(event_type, data, turn_id=turn_id))
        self.pending_events.add(task)
        task.add_done_callback(self.pending_events.discard)

    async def flush(self) -> None:
        while self.pending_events:
            await asyncio.gather(*tuple(self.pending_events), return_exceptions=True)

    async def __call__(
        self,
        event_type: str,
        data: dict[str, Any],
        *,
        turn_id: str | None = None,
    ) -> None:
        self.sequence += 1
        payload = make_event(
            event_type,
            self.call_id,
            self.tenant_id,
            data,
            turn_id=turn_id,
            sequence=self.sequence,
        )
        if event_type == "transcript_turn":
            self.transcript.append(
                {
                    "speaker": data.get("speaker", "assistant"),
                    "text": data.get("text", ""),
                    "turn_id": turn_id,
                    "interrupted": False,
                }
            )
        elif event_type == "interrupted":
            for item in reversed(self.transcript):
                if item["turn_id"] == turn_id and item["speaker"] == "assistant":
                    item["interrupted"] = True
                    break
        await self.room.local_participant.publish_data(
            json.dumps(payload, separators=(",", ":")), reliable=True, topic="aria.call-event"
        )


def _latest_user_text(chat_ctx: ChatContext) -> str:
    for item in reversed(chat_ctx.items):
        if isinstance(item, ChatMessage) and item.role == "user":
            return (item.text_content or "").strip()
    return ""


def _build_stt(settings: VoiceSettings) -> Any:
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is required for real voice mode")
    if settings.stt_mode == "realtime" and not settings.realtime_enabled:
        raise RuntimeError(
            "SARVAM_REALTIME_ENABLED must be true for this Phase 2 voice configuration"
        )
    if settings.stt_mode == "realtime":
        return sarvam.STTRealtime(language="en-IN", stream_type="fast", api_key=api_key)
    return sarvam.STT(
        language="en-IN",
        model=os.getenv("STT_MODEL", "saaras:v3"),
        api_key=api_key,
    )


def _metadata(ctx: agents.JobContext) -> tuple[str, str, str]:
    try:
        meta = json.loads(ctx.job.metadata or "{}")
    except json.JSONDecodeError:
        meta = {}
    call_id = meta.get("call_id") if isinstance(meta, dict) else None
    tenant_id = meta.get("tenant_id") if isinstance(meta, dict) else None
    mode = meta.get("mode") if isinstance(meta, dict) else None
    return str(call_id or ctx.room.name), str(tenant_id or "aura"), str(mode or "voice")


def _metric_ms(metrics: Any, name: str) -> int | None:
    value = getattr(metrics, name, None) if metrics is not None else None
    return round(value * 1000) if isinstance(value, (float, int)) and value >= 0 else None


class _ClientMessages:
    """One bounded listener for the entire call, including voice-to-text startup."""

    def __init__(self, room: Any, publisher: EventPublisher) -> None:
        self.room = room
        self.publisher = publisher
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=32)
        self.stop = asyncio.Event()
        self.last_activity = time.monotonic()
        self.activity_callback: Any = None
        self._listeners = [
            ("data_received", self._on_data),
            ("participant_disconnected", self._on_disconnect),
            ("disconnected", self._on_disconnect),
        ]
        for name, callback in self._listeners:
            room.on(name, callback)

    def activity(self) -> None:
        self.last_activity = time.monotonic()
        if self.activity_callback is not None:
            self.activity_callback()

    def _on_disconnect(self, *_args: Any) -> None:
        self.stop.set()

    def _on_data(self, packet: Any) -> None:
        if getattr(packet, "topic", None) != "aria.client-message":
            return
        try:
            data = bytes(packet.data)
            if len(data) > 16_384:
                return
            message = json.loads(data.decode("utf-8"))
        except (TypeError, ValueError, UnicodeDecodeError):
            return
        if not isinstance(message, dict):
            return
        if message.get("type") == "end_call":
            self.stop.set()
            return
        text = message.get("text")
        if (
            message.get("type") != "text_input"
            or not isinstance(text, str)
            or not text.strip()
            or len(text) > 2_000
            or self.stop.is_set()
        ):
            return
        self.activity()
        try:
            self.queue.put_nowait(text.strip())
        except asyncio.QueueFull:
            self.publisher.schedule(
                "error",
                {
                    "code": "TEXT_MODE_TURN_FAILED",
                    "message": "Please wait for a reply before sending more messages.",
                },
            )

    async def until_stopped(self, awaitable: Any) -> Any:
        operation = asyncio.ensure_future(awaitable)
        stopped = asyncio.create_task(self.stop.wait())
        try:
            await asyncio.wait((operation, stopped), return_when=asyncio.FIRST_COMPLETED)
            if self.stop.is_set():
                return None
            return await operation
        finally:
            for task in (operation, stopped):
                if not task.done():
                    task.cancel()
            await asyncio.gather(operation, stopped, return_exceptions=True)

    def close(self) -> None:
        self.stop.set()
        self.activity_callback = None
        for name, callback in self._listeners:
            self.room.off(name, callback)


async def _create_brain(publisher: EventPublisher, *, real: bool) -> Brain:
    clock = SystemClock()
    config = TenantConfigLoader(Path(__file__).resolve().parents[3]).load(publisher.tenant_id)
    state = CallState()
    llm_mode = os.getenv("LLM_MODE", "auto" if real else "mock").strip().lower()
    if real and llm_mode == "mock":
        raise RuntimeError("Real mode cannot use a mock LLM")
    if llm_mode == "auto":

        async def publish_failover(from_provider: str, to_provider: str) -> None:
            await publisher(
                "provider_failover",
                {
                    "kind": "llm",
                    "from_provider": from_provider,
                    "to_provider": to_provider,
                },
            )

        configured_candidates = os.getenv("LLM_MODEL_CANDIDATES", "").strip()
        candidates = (
            [name.strip() for name in configured_candidates.split(",") if name.strip()]
            if configured_candidates
            else list(config["providers"]["llm"]["model_candidates"])
        )
        provider = await create_real_llm(candidates, publish_failover)
    else:
        provider = create_llm(llm_mode)
    return Brain(
        config,
        state,
        provider,
        ToolDispatcher(InMemoryOrderRepository(clock), state, config, clock.now),
    )


async def _run_text_mode(
    ctx: agents.JobContext,
    publisher: EventPublisher,
    call_id: str,
    max_call_seconds: int,
    brain: Brain | None = None,
    *,
    messages: _ClientMessages | None = None,
    deadline: float | None = None,
    fallback: dict[str, str] | None = None,
) -> None:
    """A single serial consumer, using the same Brain after voice cleanup."""
    owned_messages = messages is None
    messages = messages or _ClientMessages(ctx.room, publisher)
    deadline = deadline if deadline is not None else time.monotonic() + max_call_seconds

    async def process_text(text: str) -> None:
        turn_id = f"turn-{state.turn_count + 1}"
        await publisher("state_changed", {"state": "THINKING"}, turn_id=turn_id)
        await publisher(
            "transcript_turn",
            {
                "speaker": "user",
                "text": text.strip(),
                "stt_final_ms": None,
                "llm_first_token_ms": None,
                "tts_first_byte_ms": None,
                "end_to_end_ms": None,
            },
            turn_id=turn_id,
        )
        try:
            async for brain_event in resolved_brain.handle_turn(UserTurn(text.strip())):
                if brain_event.kind == "TOOL_CALL":
                    await publisher(
                        "tool_called",
                        {
                            "tool_name": str(brain_event.payload.get("name", "unknown")),
                            "arguments": brain_event.payload.get("arguments") or {},
                        },
                        turn_id=turn_id,
                    )
                elif brain_event.kind == "TOOL_RESULT":
                    result = brain_event.payload.get("result", {})
                    await publisher(
                        "tool_result",
                        {
                            "tool_name": str(brain_event.payload.get("name", "unknown")),
                            "ok": bool(result.get("ok")) if isinstance(result, dict) else False,
                            "error_code": (
                                result.get("error_code") if isinstance(result, dict) else None
                            ),
                            "speakable_hint": (
                                result.get("speakable_hint") if isinstance(result, dict) else None
                            ),
                        },
                        turn_id=turn_id,
                    )
                elif brain_event.kind == "DONE" and brain_event.payload.get("guardrail_triggered"):
                    await publisher(
                        "guardrail_triggered",
                        {"rule": "output_validator"},
                        turn_id=turn_id,
                    )
                elif brain_event.kind == "SENTENCE":
                    answer = str(brain_event.payload.get("text", ""))
                    await publisher(
                        "transcript_turn",
                        {
                            "speaker": "assistant",
                            "text": answer,
                            "stt_final_ms": None,
                            "llm_first_token_ms": None,
                            "tts_first_byte_ms": None,
                            "end_to_end_ms": None,
                        },
                        turn_id=turn_id,
                    )
        except Exception as exc:
            logger.error(
                json.dumps(
                    {
                        "event": "text_mode_turn_failed",
                        "error_type": type(exc).__name__,
                        "call_id": call_id,
                        "tenant_id": publisher.tenant_id,
                    }
                )
            )
            await publisher(
                "error",
                {
                    "code": "TEXT_MODE_TURN_FAILED",
                    "message": "I couldn't process that. Please try again.",
                },
                turn_id=turn_id,
            )
            await publisher(
                "transcript_turn",
                {
                    "speaker": "assistant",
                    "text": (
                        "I can't reach the support service right now. Please try again shortly."
                    ),
                    "stt_final_ms": None,
                    "llm_first_token_ms": None,
                    "tts_first_byte_ms": None,
                    "end_to_end_ms": None,
                },
                turn_id=turn_id,
            )

        if not messages.stop.is_set():
            await publisher("state_changed", {"state": "LISTENING"}, turn_id=turn_id)

    async def consume() -> None:
        while not messages.stop.is_set():
            text = await messages.queue.get()
            try:
                await process_text(text)
            finally:
                messages.queue.task_done()

    try:
        async with asyncio.timeout_at(deadline):
            if brain is None:
                try:
                    brain = await messages.until_stopped(
                        _create_brain(
                            publisher,
                            real=os.getenv("VOICE_MODE", "mock").strip().lower() == "real",
                        )
                    )
                except Exception as exc:
                    _log_failure(publisher, "brain_initialization_failed", exc)
                    await publisher(
                        "error",
                        {
                            "code": "VOICE_UNAVAILABLE",
                            "message": (
                                "The support service is unavailable. Please try again shortly."
                            ),
                        },
                    )
                    return
            if messages.stop.is_set():
                return
            assert brain is not None
            resolved_brain = brain
            publisher.summary_state = resolved_brain.state
            state = resolved_brain.state
            await publisher("state_changed", {"state": "LISTENING"}, turn_id="turn-0")
            if fallback is not None and not messages.stop.is_set():
                await publisher("provider_failover", fallback)
            await messages.until_stopped(consume())
    finally:
        if owned_messages:
            messages.close()


def _log_failure(publisher: EventPublisher, event: str, exc: BaseException) -> None:
    logger.error(
        json.dumps(
            {
                "event": event,
                "error_type": type(exc).__name__,
                "call_id": publisher.call_id,
                "tenant_id": publisher.tenant_id,
            }
        )
    )


def _state_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").lower()


async def _record_usage(
    publisher: EventPublisher,
    call_id: str,
    *,
    agent_seconds: int,
    stt_seconds: int,
    tts_characters: int,
) -> None:
    try:
        await publisher.flush()
        await publisher("usage_tick", {"agent_seconds": agent_seconds})
    except Exception as exc:
        logger.error(
            json.dumps(
                {
                    "event": "usage_event_publish_failed",
                    "error_type": type(exc).__name__,
                    "call_id": call_id,
                    "tenant_id": publisher.tenant_id,
                }
            )
        )
    try:
        await SupabaseUsageMeter.from_env().complete_call(
            call_id,
            agent_seconds=agent_seconds,
            stt_seconds=stt_seconds,
            tts_characters=tts_characters,
        )
    except Exception as exc:
        logger.error(
            json.dumps(
                {
                    "event": "usage_update_failed",
                    "error_type": type(exc).__name__,
                    "call_id": call_id,
                    "tenant_id": publisher.tenant_id,
                }
            )
        )
    try:
        await publisher(
            "call_ended",
            {
                "reason": "session_closed",
                "transcript": publisher.transcript,
                "summary": deterministic_summary(publisher.summary_state),
            },
        )
    except Exception as exc:
        logger.error(
            json.dumps(
                {
                    "event": "call_end_event_publish_failed",
                    "error_type": type(exc).__name__,
                    "call_id": call_id,
                    "tenant_id": publisher.tenant_id,
                }
            )
        )


server = agents.AgentServer()


async def _run_voice(
    ctx: agents.JobContext,
    publisher: EventPublisher,
    brain: Brain,
    session: AgentSession[Any],
    agent: BrainAgent,
    closer: _SessionCloser,
    messages: _ClientMessages,
) -> None:
    state = brain.state
    idle_prompted = False
    session_closed = asyncio.Event()
    speech_tasks: set[asyncio.Future[Any]] = set()

    def reset_idle() -> None:
        nonlocal idle_prompted
        idle_prompted = False
        session.reset_away_timer()

    def speech_finished(task: asyncio.Future[Any]) -> None:
        speech_tasks.discard(task)
        if not task.cancelled() and (exc := task.exception()) is not None:
            _log_failure(publisher, "idle_speech_failed", exc)
            agent.request_fallback("tts", "sarvam_tts")

    messages.activity_callback = reset_idle

    @session.on("agent_state_changed")
    def on_agent_state_changed(ev: Any) -> None:
        raw_state = getattr(ev, "new_state", None) or getattr(ev, "state", "listening")
        state_name = _state_value(raw_state).upper()
        mapped = (
            state_name
            if state_name in {"CONNECTING", "LISTENING", "THINKING", "SPEAKING", "ENDED"}
            else "LISTENING"
        )
        publisher.schedule(
            "state_changed",
            {"state": mapped},
            turn_id=f"turn-{max(1, state.turn_count)}",
        )

    @session.on("conversation_item_added")
    def on_conversation_item_added(ev: Any) -> None:
        item = getattr(ev, "item", None)
        if not isinstance(item, ChatMessage):
            return
        text = item.text_content or ""
        metrics = getattr(item, "metrics", None)
        if item.role == "user":
            messages.activity()
            publisher.schedule(
                "transcript_turn",
                {
                    "speaker": "user",
                    "text": text,
                    "stt_final_ms": _metric_ms(metrics, "transcription_delay"),
                    "llm_first_token_ms": None,
                    "tts_first_byte_ms": None,
                    "end_to_end_ms": None,
                },
                turn_id=f"turn-{max(1, state.turn_count)}",
            )
            return
        if item.role != "assistant":
            return
        if agent._interrupted or getattr(item, "interrupted", False):
            brain.commit_spoken(text)
            agent._interrupted = False
            publisher.schedule(
                "interrupted",
                {"spoken_text": text},
                turn_id=f"turn-{max(1, state.turn_count)}",
            )
        publisher.schedule(
            "transcript_turn",
            {
                "speaker": "assistant",
                "text": text,
                "stt_final_ms": _metric_ms(metrics, "transcription_delay"),
                "llm_first_token_ms": _metric_ms(metrics, "llm_node_ttft"),
                "tts_first_byte_ms": _metric_ms(metrics, "tts_node_ttfb"),
                "end_to_end_ms": _metric_ms(metrics, "e2e_latency"),
            },
            turn_id=f"turn-{max(1, state.turn_count)}",
        )

    @session.on("overlapping_speech")
    def on_overlapping_speech(ev: Any) -> None:
        if bool(getattr(ev, "is_interruption", False)):
            agent._interrupted = True

    @session.on("agent_false_interruption")
    def on_false_interruption(_ev: Any) -> None:
        agent._interrupted = False

    @session.on("error")
    def on_session_error(ev: Any) -> None:
        error = getattr(ev, "error", None)
        source = getattr(ev, "source", None)
        kind = "tts" if source is session.tts else "llm" if source is agent.llm else "stt"
        provider = {"tts": "sarvam_tts", "llm": "configured_llm", "stt": "sarvam_stt"}[kind]
        exception = getattr(error, "error", None)
        status = getattr(exception, "status_code", None)
        logger.warning(
            json.dumps(
                {
                    "event": "provider_error",
                    "provider": provider,
                    "error_type": type(exception if exception is not None else error).__name__,
                    "status_code": status
                    if isinstance(status, int) and 100 <= status <= 599
                    else None,
                    "recoverable": bool(getattr(error, "recoverable", False)),
                    "call_id": publisher.call_id,
                    "tenant_id": publisher.tenant_id,
                }
            )
        )
        if getattr(error, "recoverable", False) or messages.stop.is_set():
            return
        agent.request_fallback(kind, provider)

    @session.on("user_state_changed")
    def on_user_state_changed(ev: Any) -> None:
        nonlocal idle_prompted
        new_state = _state_value(getattr(ev, "new_state", None))
        if new_state == "speaking":
            messages.activity()
            return
        if new_state != "away" or messages.stop.is_set() or agent.fallback_requested:
            return
        if not idle_prompted:
            idle_prompted = True
            sentence = "Are you still there?"
            if not agent._within_tts_cap(sentence):
                agent.request_fallback("tts", "sarvam_tts")
                return
            task = asyncio.ensure_future(session.say(sentence, allow_interruptions=True))
            speech_tasks.add(task)
            task.add_done_callback(speech_finished)
            session.reset_away_timer()
            return
        closer.request()

    @session.on("close")
    def on_close(_ev: Any) -> None:
        session_closed.set()

    try:
        await messages.until_stopped(
            session.start(
                room=ctx.room,
                agent=agent,
                record={"audio": False},
                room_options=room_io.RoomOptions(
                    text_input=False,
                    close_on_disconnect=False,
                    delete_room_on_close=False,
                ),
            )
        )
        if messages.stop.is_set() or closer.task is not None:
            return
        await publisher("state_changed", {"state": "LISTENING"}, turn_id="turn-0")
        greeting = "Hello, I'm Aria from Aura Skincare. How can I help you today?"
        if not agent._within_tts_cap(greeting):
            await agent._signal_tts_cap()
            return
        # A terminal error can happen during greeting; closing the session will
        # finish its speech handle, while end/disconnect cancels our waiter.
        await messages.until_stopped(session.say(greeting))
        await messages.until_stopped(session_closed.wait())
    finally:
        messages.activity_callback = None
        try:
            await closer.wait()
        finally:
            tasks = tuple(speech_tasks)
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            session.off("agent_state_changed", on_agent_state_changed)
            session.off("conversation_item_added", on_conversation_item_added)
            session.off("overlapping_speech", on_overlapping_speech)
            session.off("agent_false_interruption", on_false_interruption)
            session.off("error", on_session_error)
            session.off("user_state_changed", on_user_state_changed)
            session.off("close", on_close)


@server.rtc_session(agent_name=os.getenv("LIVEKIT_AGENT_NAME", "aria-voice"))
async def entrypoint(ctx: agents.JobContext) -> None:
    started = time.monotonic()
    call_id, tenant_id, requested_mode = _metadata(ctx)
    publisher = EventPublisher(ctx.room, call_id, tenant_id)
    messages = _ClientMessages(ctx.room, publisher)
    settings: VoiceSettings | None = None
    brain: Brain | None = None
    agent: BrainAgent | None = None
    closer: _SessionCloser | None = None
    voice_providers: list[Any] = []
    stt_started_at: float | None = None
    stt_seconds = 0
    voice_closed = False

    async def close_voice() -> None:
        nonlocal stt_started_at, stt_seconds, voice_closed
        if voice_closed:
            return
        voice_closed = True
        if closer is not None:
            try:
                await closer.wait()
            except Exception as exc:
                _log_failure(publisher, "voice_cleanup_failed", exc)
                # Never allow a still-running voice Brain to race text inference.
                messages.stop.set()
                publisher.schedule(
                    "error",
                    {
                        "code": "CONNECTION_FAILED",
                        "message": "This call could not continue safely. Please start a new call.",
                    },
                )
        if stt_started_at is not None:
            stt_seconds += max(0, round(time.monotonic() - stt_started_at))
            stt_started_at = None
        while voice_providers:
            provider = voice_providers.pop()
            close = getattr(provider, "aclose", None)
            if close is not None:
                try:
                    await close()
                except Exception as exc:
                    _log_failure(publisher, "provider_cleanup_failed", exc)

    try:
        settings = VoiceSettings.from_env()
        deadline = started + settings.max_call_seconds
        async with asyncio.timeout_at(deadline):
            await messages.until_stopped(ctx.connect())
            if messages.stop.is_set():
                return
            await publisher("state_changed", {"state": "CONNECTING"}, turn_id="turn-0")
            brain = await messages.until_stopped(
                _create_brain(
                    publisher,
                    real=settings.mode == "real",
                )
            )
            if messages.stop.is_set():
                return
            publisher.summary_state = brain.state
            if settings.mode != "real" or requested_mode == "text":
                await _run_text_mode(
                    ctx,
                    publisher,
                    call_id,
                    settings.max_call_seconds,
                    brain,
                    messages=messages,
                    deadline=deadline,
                    fallback=None
                    if requested_mode == "text"
                    else {
                        "kind": "stt",
                        "from_provider": "voice_disabled",
                        "to_provider": "text_mode",
                    },
                )
                return

            fallback = None
            failure_kind, failure_provider = "stt", "sarvam_voice"
            try:
                if not all(
                    os.getenv(name)
                    for name in (
                        "LIVEKIT_URL",
                        "LIVEKIT_API_KEY",
                        "LIVEKIT_API_SECRET",
                    )
                ):
                    raise RuntimeError(
                        "LiveKit server credentials are required for real voice mode"
                    )
                stt = _build_stt(settings)
                voice_providers.append(stt)
                if messages.stop.is_set():
                    return
                failure_kind, failure_provider = "tts", "sarvam_tts"
                tts = sarvam.TTS(
                    target_language_code="en-IN",
                    model="bulbul:v3",
                    speaker=os.getenv("SARVAM_TTS_SPEAKER", "shubh"),
                    api_key=os.getenv("SARVAM_API_KEY"),
                    output_audio_codec="linear16",
                )
                voice_providers.append(tts)
                if messages.stop.is_set():
                    return
                failure_kind, failure_provider = "stt", "sarvam_voice"
                session: AgentSession[Any] = AgentSession(
                    stt=stt,
                    tts=tts,
                    vad=None,
                    user_away_timeout=float(settings.idle_timeout_seconds),
                    turn_handling=TurnHandlingOptions(
                        turn_detection="stt",
                        endpointing={"min_delay": 0.0, "max_delay": 0.0},
                        interruption={"enabled": True, "mode": "vad"},
                        preemptive_generation={"enabled": False},
                    ),
                    conn_options=SessionConnectOptions(
                        stt_conn_options=APIConnectOptions(max_retry=0),
                        tts_conn_options=APIConnectOptions(max_retry=0),
                        max_unrecoverable_errors=0,
                    ),
                )
                closer = _SessionCloser(session)
                agent = BrainAgent(
                    brain,
                    publisher,
                    max_call_seconds=settings.max_call_seconds,
                    max_tts_characters=settings.per_call_tts_characters_cap,
                    call_started_at=started,
                )
                agent.shutdown_session = closer.request
                stt_started_at = time.monotonic()
                await _run_voice(ctx, publisher, brain, session, agent, closer, messages)
                if agent.fallback_requested:
                    fallback = {
                        "kind": agent.fallback_kind,
                        "from_provider": agent.fallback_provider,
                        "to_provider": "text_mode",
                    }
            except Exception as exc:
                _log_failure(publisher, "voice_session_failed", exc)
                fallback = {
                    "kind": failure_kind,
                    "from_provider": failure_provider,
                    "to_provider": "text_mode",
                }
            finally:
                await close_voice()
            if fallback is not None and not messages.stop.is_set():
                # No reconnection or second Brain: text becomes ready only after
                # all voice work has finished and the metered providers are closed.
                await publisher.flush()
                await _run_text_mode(
                    ctx,
                    publisher,
                    call_id,
                    settings.max_call_seconds,
                    brain,
                    messages=messages,
                    deadline=deadline,
                    fallback=fallback,
                )
    except TimeoutError:
        await publisher(
            "error",
            {
                "code": "CALL_DURATION_LIMIT",
                "message": "This demo call has reached its time limit. Please start a new call.",
            },
        )
    except Exception as exc:
        _log_failure(publisher, "call_initialization_failed", exc)
        await publisher(
            "error",
            {
                "code": "VOICE_UNAVAILABLE",
                "message": "The support service is unavailable. Please try again shortly.",
            },
        )
    finally:
        messages.close()
        await close_voice()
        cap = settings.max_call_seconds if settings is not None else 300
        elapsed = min(cap, max(0, round(time.monotonic() - started)))
        try:
            await _record_usage(
                publisher,
                call_id,
                agent_seconds=elapsed,
                stt_seconds=min(elapsed, stt_seconds),
                tts_characters=agent.tts_characters if agent is not None else 0,
            )
        finally:
            await ctx.room.disconnect()


if __name__ == "__main__":
    agents.cli.run_app(server)
