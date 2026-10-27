from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from livekit.agents import AgentSession, ChatContext, llm

from brain.state import CallState
from brain.turn import BrainEvent
from providers.llm.mock import MockLLM
from voice import worker
from voice.settings import VoiceSettings
from voice.worker import EventPublisher, _build_stt


def test_voice_settings_are_mock_first_and_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VOICE_MODE", raising=False)
    monkeypatch.delenv("SARVAM_STT_MODE", raising=False)

    settings = VoiceSettings.from_env()

    assert settings.mode == "mock"
    assert settings.stt_mode == "realtime"
    assert settings.realtime_enabled is True
    assert settings.max_call_seconds == 300
    assert settings.idle_timeout_seconds == 45
    assert settings.max_concurrent_calls == 4
    assert settings.monthly_stt_seconds_cap == 7_200
    assert settings.monthly_tts_characters_cap == 10_000
    assert settings.per_call_tts_characters_cap == 2_500


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("VOICE_MODE", "automatic"),
        ("SARVAM_STT_MODE", "realtime+legacy"),
        ("SARVAM_REALTIME_ENABLED", "sometimes"),
        ("STT_MODEL", "saaras:v3"),
        ("MAX_CALL_SECONDS", "301"),
        ("MAX_CONCURRENT_CALLS", "5"),
    ],
)
def test_voice_settings_reject_unknown_or_unsafe_values(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError):
        VoiceSettings.from_env()


def test_real_sarvam_mode_requires_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SARVAM_API_KEY"):
        _build_stt(VoiceSettings.from_env())


def test_event_publisher_emits_contract_valid_data() -> None:
    class LocalParticipant:
        published: list[tuple[str, str, bool]] = []

        async def publish_data(self, payload: str, *, reliable: bool, topic: str) -> None:
            self.published.append((payload, topic, reliable))

    class Room:
        local_participant = LocalParticipant()

    publisher = EventPublisher(Room(), "call-test", "aura")
    asyncio.run(
        publisher(
            "state_changed",
            {"state": "CONNECTING"},
            turn_id="turn-0",
        )
    )

    encoded, topic, reliable = Room.local_participant.published[0]
    payload = json.loads(encoded)
    schema = json.loads(
        (Path(__file__).resolve().parents[3] / "contracts" / "call_events.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    assert topic == "aria.call-event"
    assert reliable is True


def test_final_call_event_contains_local_transcript_and_summary() -> None:
    class LocalParticipant:
        published: list[str] = []

        async def publish_data(self, payload: str, *, reliable: bool, topic: str) -> None:
            assert reliable is True
            assert topic == "aria.call-event"
            self.published.append(payload)

    class Room:
        local_participant = LocalParticipant()

    publisher = EventPublisher(Room(), "call-final", "aura")

    async def publish_final() -> None:
        await publisher("transcript_turn", {"speaker": "user", "text": "hello"}, turn_id="turn-1")
        await publisher(
            "call_ended",
            {
                "reason": "session_closed",
                "transcript": publisher.transcript,
                "summary": {
                    "schema_version": 1,
                    "customer_intent": "OTHER",
                    "order_id": None,
                    "resolution_status": "UNRESOLVED",
                    "policy_outcome": None,
                    "call_summary": "The conversation was recorded.",
                    "follow_up_needed": False,
                },
            },
        )

    asyncio.run(publish_final())
    payload = json.loads(Room.local_participant.published[-1])
    schema_path = Path(__file__).resolve().parents[3] / "contracts" / "call_events.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    assert payload["data"]["transcript"][0]["text"] == "hello"
    assert payload["data"]["summary"]["customer_intent"] == "OTHER"


def test_event_publisher_flushes_scheduled_transcript_before_final_event() -> None:
    class LocalParticipant:
        published: list[str] = []

        async def publish_data(self, payload: str, *, reliable: bool, topic: str) -> None:
            self.published.append(payload)

    class Room:
        local_participant = LocalParticipant()

    publisher = EventPublisher(Room(), "call-flush", "aura")

    async def publish_and_flush() -> None:
        publisher.schedule(
            "transcript_turn",
            {"speaker": "user", "text": "where is my order"},
            turn_id="turn-1",
        )
        await publisher.flush()
        await publisher(
            "call_ended",
            {
                "reason": "session_closed",
                "transcript": publisher.transcript,
                "summary": {
                    "schema_version": 1,
                    "customer_intent": "OTHER",
                    "order_id": None,
                    "resolution_status": "UNRESOLVED",
                    "policy_outcome": None,
                    "call_summary": "The conversation was recorded.",
                    "follow_up_needed": False,
                },
            },
        )

    asyncio.run(publish_and_flush())
    payload = json.loads(Room.local_participant.published[-1])
    assert payload["event_type"] == "call_ended"
    assert payload["data"]["transcript"][0]["text"] == "where is my order"


# These doubles never open a network connection or read real provider credentials.
class FakeRoom:
    def __init__(self):
        self.name = "call-offline"
        self.listeners = {}
        self.events = []
        self.on_publish = None
        self.disconnects = 0
        self.local_participant = self

    def on(self, name, callback=None):
        def register(fn):
            self.listeners.setdefault(name, []).append(fn)
            return fn

        return register(callback) if callback is not None else register

    def off(self, name, callback):
        self.listeners[name].remove(callback)

    def emit(self, name, value):
        for callback in tuple(self.listeners.get(name, [])):
            callback(value)

    def message(self, message):
        self.emit(
            "data_received",
            SimpleNamespace(topic="aria.client-message", data=json.dumps(message).encode()),
        )

    async def publish_data(self, payload, **kwargs):
        event = json.loads(payload)
        self.events.append(event)
        if self.on_publish:
            self.on_publish(event)

    async def disconnect(self):
        assert self.events[-1]["event_type"] == "call_ended"
        self.disconnects += 1


class FakeCtx:
    def __init__(self, room, mode="voice"):
        self.room = room
        self.job = SimpleNamespace(metadata=json.dumps({"mode": mode}))
        self.on_connect = None

    async def connect(self):
        if self.on_connect:
            self.on_connect()


class FakeBrain:
    def __init__(self, fail=False):
        self.state = CallState()
        self.seen = []
        self.active = 0
        self.max_active = 0
        self.finished = 0
        self.fail = fail
        self.on_turn = None

    async def handle_turn(self, turn):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.seen.append(turn.text)
        self.state.turn_count += 1
        try:
            if self.on_turn:
                self.on_turn()
            await asyncio.sleep(0)
            if self.fail:
                raise RuntimeError("secret-provider-key-must-not-appear")
            yield BrainEvent("SENTENCE", {"text": "The support team can help."})
            yield BrainEvent("DONE", {})
        finally:
            self.active -= 1
            self.finished += 1

    def commit_spoken(self, text):
        pass


class FakeSession(FakeRoom):
    def __init__(self, **kwargs):
        super().__init__()
        self.options = kwargs
        self.tts = kwargs.get("tts")
        self.closed = 0
        self.say_calls = []
        self.away_resets = 0
        self.on_start = None
        self.block_greeting = False

    async def start(self, *, agent, **kwargs):
        self.agent = agent
        self.start_options = kwargs
        if self.on_start:
            self.on_start(self)

    def say(self, text, **kwargs):
        self.say_calls.append(text)

        async def finish():
            if self.block_greeting:
                await asyncio.Event().wait()

        return asyncio.create_task(finish())

    async def aclose(self):
        self.closed += 1
        self.emit("close", SimpleNamespace())
        await asyncio.sleep(0)

    def reset_away_timer(self):
        self.away_resets += 1


@pytest.fixture
def offline(monkeypatch):
    for name in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "SARVAM_API_KEY"):
        monkeypatch.setenv(name, "offline-not-a-real-key")
    monkeypatch.setenv("VOICE_MODE", "real")
    monkeypatch.setenv("LLM_MODE", "auto")
    settings = replace(VoiceSettings.from_env(), max_call_seconds=0.5)
    monkeypatch.setattr(worker.VoiceSettings, "from_env", lambda: settings)
    brain = FakeBrain()
    room = FakeRoom()
    ctx = FakeCtx(room)
    sessions = []

    async def create_brain(*args, **kwargs):
        return brain

    def create_session(**kwargs):
        session = FakeSession(**kwargs)
        sessions.append(session)
        session.on_start = lambda s: room.message({"type": "end_call"})
        return session

    async def no_network_llm(*args, **kwargs):
        return SimpleNamespace()

    monkeypatch.setattr(worker, "create_real_llm", no_network_llm)
    monkeypatch.setattr(worker, "create_llm", lambda *args: SimpleNamespace())
    monkeypatch.setattr(worker, "_create_brain", create_brain, raising=False)
    monkeypatch.setattr(worker, "AgentSession", create_session)
    monkeypatch.setattr(worker, "_build_stt", lambda _: SimpleNamespace())
    monkeypatch.setattr(worker.sarvam, "TTS", lambda **_: SimpleNamespace())
    usage = []

    class Meter:
        async def complete_call(self, call_id, **kwargs):
            assert brain.active == 0
            assert not any(room.listeners.values())
            usage.append(kwargs)

    monkeypatch.setattr(worker.SupabaseUsageMeter, "from_env", lambda: Meter())
    return SimpleNamespace(
        room=room,
        ctx=ctx,
        brain=brain,
        sessions=sessions,
        usage=usage,
        settings=settings,
        create_session=create_session,
    )


def assert_finalized(env):
    assert env.room.events[-1]["event_type"] == "call_ended"
    assert len(env.usage) == 1
    assert env.room.disconnects == 1
    assert not any(env.room.listeners.values())


def test_brain_agent_supplies_sdk_llm_without_a_second_invocation():
    async def check():
        room = FakeRoom()
        brain = FakeBrain()
        agent = worker.BrainAgent(
            brain,
            EventPublisher(room, room.name, "aura"),
            max_call_seconds=300,
            max_tts_characters=2500,
            call_started_at=worker.time.monotonic(),
        )
        assert isinstance(agent.llm, llm.LLM)
        with pytest.raises(RuntimeError, match="Brain"):
            agent.llm.chat(chat_ctx=ChatContext())
        session = AgentSession(vad=None, turn_handling={"turn_detection": "manual"})
        try:
            await session.start(agent=agent, record={"audio": False})
            assert session._opts.recording_options["audio"] is False
            assert session._recorder_io is None
            handle = session.generate_reply(user_input="hello")
            await handle
            assert brain.seen == ["hello"]
        finally:
            await session.aclose()

    asyncio.run(check())


def test_shutdown_is_requested_outside_generator_and_only_once():
    async def check():
        room = FakeRoom()
        brain = FakeBrain(fail=True)
        agent = worker.BrainAgent(
            brain,
            EventPublisher(room, room.name, "aura"),
            max_call_seconds=300,
            max_tts_characters=2500,
            call_started_at=worker.time.monotonic(),
        )
        session = FakeSession()
        closer = worker._SessionCloser(session)
        agent.shutdown_session = closer.request
        context = ChatContext()
        context.add_message(role="user", content="hello")
        assert [item async for item in agent.llm_node(context, [], {})] == []
        assert brain.finished == 1
        assert not agent._interrupted
        closer.request()
        await closer.wait()
        assert session.closed == 1
        assert agent.fallback_requested
        assert not any(e["event_type"] == "provider_failover" for e in room.events)

    asyncio.run(check())


def test_session_configuration_uses_native_stt_and_zero_retries(offline):
    asyncio.run(worker.entrypoint(offline.ctx))
    session = offline.sessions[0]
    assert session.options["vad"] is None
    assert session.options["turn_handling"]["turn_detection"] == "stt"
    assert session.options["turn_handling"]["preemptive_generation"]["enabled"] is False
    assert session.options["conn_options"].stt_conn_options.max_retry == 0
    assert session.options["conn_options"].tts_conn_options.max_retry == 0
    assert session.start_options["room_options"].delete_room_on_close is False
    assert session.start_options["room_options"].text_input is False
    assert_finalized(offline)


def test_session_disables_optional_audio_recording(offline):
    asyncio.run(worker.entrypoint(offline.ctx))
    assert offline.sessions[0].start_options["record"] == {"audio": False}
    assert_finalized(offline)


def test_worker_selects_uncompressed_sarvam_audio(offline, monkeypatch):
    from livekit.plugins.sarvam.tts import TTS

    options = []

    def create_tts(**kwargs):
        options.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(worker.sarvam, "TTS", create_tts)
    asyncio.run(worker.entrypoint(offline.ctx))
    assert options[0]["output_audio_codec"] == "linear16"
    provider = TTS(**options[0])
    assert provider._opts.output_audio_codec == "linear16"
    assert provider.model == "bulbul:v3"
    assert_finalized(offline)


def test_sarvam_pcm_stream_emits_frames_without_compressed_decoder(monkeypatch):
    import base64

    from livekit import rtc
    from livekit.agents import APIConnectOptions
    from livekit.agents.utils import codecs
    from livekit.plugins.sarvam.tts import TTS, SynthesizeStream

    pcm = b"\x01\x00" * 2205

    def reject_decoder(*args, **kwargs):
        raise AssertionError("PCM must not invoke the compressed audio decoder")

    async def synthetic_response(stream, word_stream, emitter):
        sentences = [item.token async for item in word_stream]
        assert sentences == ["Hello from Aria."]
        emitter.start_segment(segment_id="offline-pcm")
        for chunk in (pcm[:701], pcm[701:]):
            await stream._handle_audio_message(
                {"data": {"audio": base64.b64encode(chunk).decode("ascii")}}, emitter
            )
        emitter.end_segment()

    monkeypatch.setattr(codecs, "AudioStreamDecoder", reject_decoder)
    monkeypatch.setattr(SynthesizeStream, "_run_ws", synthetic_response)

    async def check():
        provider = TTS(
            api_key="offline-not-a-real-key", model="bulbul:v3", output_audio_codec="linear16"
        )
        stream = provider.stream(conn_options=APIConnectOptions(max_retry=0))
        source = rtc.AudioSource(sample_rate=48000, num_channels=1)
        try:
            stream.push_text("Hello from Aria.")
            stream.end_input()
            async with asyncio.timeout(3):
                frames = [event.frame async for event in stream]
                assert frames
                assert b"".join(bytes(frame.data) for frame in frames) == pcm
                assert all(
                    frame.sample_rate == 22050 and frame.num_channels == 1 for frame in frames
                )
                resampler = rtc.AudioResampler(22050, 48000)
                output = [item for frame in frames for item in resampler.push(frame)]
                output.extend(resampler.flush())
                assert sum(frame.samples_per_channel for frame in output) == 4800
                for frame in output:
                    await source.capture_frame(frame)
        finally:
            await stream.aclose()
            await provider.aclose()
            await source.aclose()

    asyncio.run(check())


@pytest.mark.parametrize("recoverable", [True, False])
def test_provider_errors_only_terminal_fall_back_and_never_expose_secrets(
    offline,
    monkeypatch,
    caplog,
    recoverable,
):
    def create_session(**kwargs):
        session = offline.create_session(**kwargs)

        def start(s):
            error = SimpleNamespace(
                recoverable=recoverable,
                error=SimpleNamespace(status_code=429),
                message="secret-provider-key-must-not-appear",
            )
            s.emit("error", SimpleNamespace(error=error, source=s.options["tts"]))
            if recoverable:
                assert s.agent.fallback_requested is False
                offline.room.message({"type": "end_call"})
            else:
                offline.room.message({"type": "text_input", "text": "continue please"})

        session.on_start = start
        return session

    monkeypatch.setattr(worker, "AgentSession", create_session)
    offline.room.on_publish = lambda e: (
        offline.room.message({"type": "end_call"})
        if e["event_type"] == "transcript_turn" and e["data"]["speaker"] == "assistant"
        else None
    )
    asyncio.run(worker.entrypoint(offline.ctx))
    failovers = [e for e in offline.room.events if e["event_type"] == "provider_failover"]
    assert bool(failovers) is not recoverable
    if not recoverable:
        assert offline.brain.seen == ["continue please"]
        assert failovers[0]["data"]["kind"] == "tts"
    assert "secret-provider-key-must-not-appear" not in caplog.text
    assert "secret-provider-key-must-not-appear" not in json.dumps(offline.room.events)
    assert_finalized(offline)


def test_early_text_is_buffered_and_processed_serially_on_the_same_brain(offline, monkeypatch):
    offline.brain.state.turn_count = 4  # State from voice must survive the handover.

    def fail_stt(_):
        offline.room.message({"type": "text_input", "text": "first"})
        offline.room.message({"type": "text_input", "text": "second"})
        raise RuntimeError("offline access failure")

    monkeypatch.setattr(worker, "_build_stt", fail_stt)

    def overlapping_message():
        if len(offline.brain.seen) == 1:
            offline.room.message({"type": "text_input", "text": "third"})

    offline.brain.on_turn = overlapping_message

    def end_after_three(event):
        if event["event_type"] == "transcript_turn" and event["data"]["speaker"] == "assistant":
            assert not offline.sessions or offline.sessions[0].closed == 1
            if len(offline.brain.seen) == 3:
                offline.room.message({"type": "end_call"})

    offline.room.on_publish = end_after_three
    asyncio.run(worker.entrypoint(offline.ctx))
    assert offline.brain.seen == ["first", "second", "third"]
    assert offline.brain.max_active == 1
    assert offline.brain.state.turn_count == 7
    turns = [e for e in offline.room.events if e["event_type"] == "transcript_turn"]
    assert [e["turn_id"] for e in turns if e["data"]["speaker"] == "user"] == [
        "turn-5",
        "turn-6",
        "turn-7",
    ]
    states = [e["data"]["state"] for e in offline.room.events if e["event_type"] == "state_changed"]
    assert states.count("THINKING") == 3
    assert states.count("LISTENING") >= 3
    assert_finalized(offline)


@pytest.mark.parametrize("control", ["end_call", "disconnect"])
def test_early_end_or_disconnect_stops_initialization(offline, control):
    def end():
        offline.room.message({"type": "text_input", "text": "must not run"})
        if control == "end_call":
            offline.room.message({"type": "end_call"})
        else:
            offline.room.emit("participant_disconnected", SimpleNamespace())

    offline.ctx.on_connect = end
    asyncio.run(worker.entrypoint(offline.ctx))
    assert offline.brain.seen == []
    assert offline.sessions == []
    assert_finalized(offline)


def test_brain_initialization_failure_is_explicit_and_finalizes(offline, monkeypatch, caplog):
    async def fail(*args, **kwargs):
        raise RuntimeError("secret-provider-key-must-not-appear")

    monkeypatch.setattr(worker, "_create_brain", fail)
    asyncio.run(worker.entrypoint(offline.ctx))
    errors = [e for e in offline.room.events if e["event_type"] == "error"]
    assert errors and errors[0]["data"]["code"] == "VOICE_UNAVAILABLE"
    assert not any(e["event_type"] == "provider_failover" for e in offline.room.events)
    assert offline.sessions == []
    assert "secret-provider-key-must-not-appear" not in caplog.text
    assert_finalized(offline)


def test_deliberately_requested_text_has_no_fallback_notice(offline):
    offline.ctx.job.metadata = json.dumps({"mode": "text"})
    offline.room.on_publish = lambda e: (
        offline.room.message({"type": "end_call"})
        if e["event_type"] == "state_changed" and e["data"]["state"] == "LISTENING"
        else None
    )
    asyncio.run(worker.entrypoint(offline.ctx))
    assert offline.sessions == []
    assert not any(e["event_type"] == "provider_failover" for e in offline.room.events)
    assert_finalized(offline)


def test_absolute_deadline_includes_greeting(offline, monkeypatch):
    monkeypatch.setattr(
        worker.VoiceSettings,
        "from_env",
        lambda: replace(
            offline.settings,
            max_call_seconds=0.02,
        ),
    )

    def create_session(**kwargs):
        s = offline.create_session(**kwargs)
        s.on_start = None
        s.block_greeting = True
        return s

    monkeypatch.setattr(worker, "AgentSession", create_session)
    asyncio.run(worker.entrypoint(offline.ctx))
    assert any(
        e["event_type"] == "error" and e["data"]["code"] == "CALL_DURATION_LIMIT"
        for e in offline.room.events
    )
    assert offline.sessions[0].closed == 1
    assert_finalized(offline)


def test_idle_accepts_strings_and_enums_and_resets_on_activity(offline, monkeypatch):
    class UserState(Enum):
        AWAY = "away"
        SPEAKING = "speaking"

    def create_session(**kwargs):
        s = offline.create_session(**kwargs)

        def start(session):
            session.emit("user_state_changed", SimpleNamespace(new_state="away"))
            session.emit("user_state_changed", SimpleNamespace(new_state=UserState.SPEAKING))
            session.emit("user_state_changed", SimpleNamespace(new_state=UserState.AWAY))
            session.emit("user_state_changed", SimpleNamespace(new_state="away"))

        s.on_start = start
        return s

    monkeypatch.setattr(worker, "AgentSession", create_session)
    asyncio.run(worker.entrypoint(offline.ctx))
    assert offline.sessions[0].say_calls.count("Are you still there?") == 2
    assert offline.sessions[0].away_resets >= 2
    assert offline.sessions[0].closed == 1
    assert_finalized(offline)


def test_real_mode_cannot_silently_construct_mock_brain(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "mock")
    room = FakeRoom()
    with pytest.raises(RuntimeError, match="mock"):
        asyncio.run(worker._create_brain(EventPublisher(room, room.name, "aura"), real=True))


@pytest.mark.parametrize("failure_at", ["tts", "session", "start"])
def test_voice_initialization_failures_handover_after_cleanup(offline, monkeypatch, failure_at):
    closed_providers = []

    class Provider:
        async def aclose(self):
            closed_providers.append(self)

    stt, tts = Provider(), Provider()
    monkeypatch.setattr(worker, "_build_stt", lambda _: stt)

    def build_tts(**kwargs):
        if failure_at == "tts":
            raise RuntimeError("secret-init-failure")
        return tts

    monkeypatch.setattr(worker.sarvam, "TTS", build_tts)

    def build_session(**kwargs):
        if failure_at == "session":
            raise RuntimeError("secret-init-failure")
        session = offline.create_session(**kwargs)

        async def start(**kwargs):
            raise RuntimeError("secret-init-failure")

        session.start = start
        return session

    monkeypatch.setattr(worker, "AgentSession", build_session)

    def on_publish(event):
        if event["event_type"] == "provider_failover":
            assert stt in closed_providers
            if failure_at == "tts":
                assert event["data"]["kind"] == "tts"
            if failure_at != "tts":
                assert tts in closed_providers
            if offline.sessions:
                assert offline.sessions[0].closed == 1
            offline.room.message({"type": "text_input", "text": "still here"})
        elif event["event_type"] == "transcript_turn" and event["data"]["speaker"] == "assistant":
            offline.room.message({"type": "end_call"})

    offline.room.on_publish = on_publish
    asyncio.run(worker.entrypoint(offline.ctx))
    assert offline.brain.seen == ["still here"]
    assert len(closed_providers) == (1 if failure_at == "tts" else 2)
    assert_finalized(offline)


def test_persistent_message_queue_is_bounded_validates_and_keeps_end_active():
    async def check():
        room = FakeRoom()
        publisher = EventPublisher(room, room.name, "aura")
        messages = worker._ClientMessages(room, publisher)
        room.message({"type": "text_input", "text": " "})
        room.message({"type": "text_input", "text": "x" * 2001})
        room.emit("data_received", SimpleNamespace(topic="other", data=b"{}"))
        room.emit("data_received", SimpleNamespace(topic="aria.client-message", data=b"\xff"))
        assert messages.queue.empty()
        for _ in range(40):
            room.message({"type": "text_input", "text": "queued"})
        assert messages.queue.qsize() == messages.queue.maxsize == 32
        room.message({"type": "end_call"})
        assert messages.stop.is_set()
        messages.close()
        await publisher.flush()
        assert not any(room.listeners.values())
        assert any(e["data"]["code"] == "TEXT_MODE_TURN_FAILED" for e in room.events)

    asyncio.run(check())


@pytest.mark.parametrize("control", ["end_call", "disconnect"])
def test_end_cancels_active_serial_consumer_before_final_summary(offline, control):
    offline.ctx.job.metadata = json.dumps({"mode": "text"})
    offline.ctx.on_connect = lambda: offline.room.message({"type": "text_input", "text": "hello"})

    def stop_during_turn():
        if control == "end_call":
            offline.room.message({"type": "end_call"})
        else:
            offline.room.emit("disconnected", SimpleNamespace())

    offline.brain.on_turn = stop_during_turn
    asyncio.run(worker.entrypoint(offline.ctx))
    assert offline.brain.finished == 1
    assert offline.brain.active == 0
    assert_finalized(offline)


def test_fallback_uses_the_original_deadline_not_a_new_call_budget(offline, monkeypatch):
    captured = []
    original_text = worker._run_text_mode

    async def text(*args, **kwargs):
        captured.append(kwargs["deadline"])
        await original_text(*args, **kwargs)

    monkeypatch.setattr(worker, "_run_text_mode", text)
    origin = worker.time.monotonic()

    def fail_stt(_):
        raise RuntimeError("offline failure")

    monkeypatch.setattr(worker, "_build_stt", fail_stt)

    def end_at_ready(event):
        if event["event_type"] == "provider_failover":
            offline.room.message({"type": "end_call"})

    offline.room.on_publish = end_at_ready
    asyncio.run(worker.entrypoint(offline.ctx))
    assert origin < captured[0] <= origin + offline.settings.max_call_seconds + 0.05
    assert_finalized(offline)


def test_deadline_cancels_brain_initialization_and_finalizes(offline, monkeypatch):
    monkeypatch.setattr(
        worker.VoiceSettings,
        "from_env",
        lambda: replace(
            offline.settings,
            max_call_seconds=0.02,
        ),
    )
    finalized = []

    async def initialize(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            finalized.append(True)

    monkeypatch.setattr(worker, "_create_brain", initialize)
    asyncio.run(worker.entrypoint(offline.ctx))
    assert finalized == [True]
    assert offline.sessions == []
    assert any(
        e["event_type"] == "error" and e["data"]["code"] == "CALL_DURATION_LIMIT"
        for e in offline.room.events
    )
    assert_finalized(offline)


def test_tts_allowance_counts_greeting_idle_and_brain_output(offline, monkeypatch):
    async def run():
        def build_session(**kwargs):
            session = offline.create_session(**kwargs)
            session.on_start = None
            original_say = session.say

            def say(text, **kwargs):
                handle = original_say(text, **kwargs)
                if text.startswith("Hello"):
                    session.emit("user_state_changed", SimpleNamespace(new_state="away"))
                    context = ChatContext()
                    context.add_message(role="user", content="hello")

                    async def answer():
                        async for _ in session.agent.llm_node(context, [], {}):
                            pass
                        offline.room.message({"type": "end_call"})

                    tasks.append(asyncio.create_task(answer()))
                return handle

            session.say = say
            return session

        monkeypatch.setattr(worker, "AgentSession", build_session)
        tasks = []
        await worker.entrypoint(offline.ctx)
        await asyncio.gather(*tasks)

    asyncio.run(run())
    session = offline.sessions[0]
    expected = sum(len(s) for s in session.say_calls) + len("The support team can help.")
    assert session.agent.tts_characters == expected
    assert offline.usage[0]["tts_characters"] == expected
    assert_finalized(offline)


def test_idle_prompt_cannot_bypass_tts_cap(offline, monkeypatch):
    monkeypatch.setattr(
        worker.VoiceSettings,
        "from_env",
        lambda: replace(
            offline.settings,
            per_call_tts_characters_cap=100,
        ),
    )

    def create_session(**kwargs):
        session = offline.create_session(**kwargs)
        session.on_start = None
        original_say = session.say

        def say(text, **kwargs):
            result = original_say(text, **kwargs)
            if text.startswith("Hello"):
                session.agent.tts_characters = 99
                session.emit("user_state_changed", SimpleNamespace(new_state="away"))
            return result

        session.say = say
        return session

    monkeypatch.setattr(worker, "AgentSession", create_session)
    offline.room.on_publish = lambda e: (
        offline.room.message({"type": "end_call"})
        if e["event_type"] == "provider_failover"
        else None
    )
    asyncio.run(worker.entrypoint(offline.ctx))
    assert "Are you still there?" not in offline.sessions[0].say_calls
    assert offline.sessions[0].agent.fallback_requested
    assert_finalized(offline)


def test_actual_brain_preserves_order_confirmation_across_text_handover(monkeypatch):
    monkeypatch.setenv("VOICE_MODE", "mock")
    monkeypatch.setenv("LLM_MODE", "mock")

    async def check():
        room = FakeRoom()
        publisher = EventPublisher(room, room.name, "aura")
        messages = worker._ClientMessages(room, publisher)
        brain = await worker._create_brain(publisher, real=False)
        brain.llm = MockLLM(
            [
                {"tool_call": {"name": "get_order_details", "arguments": {"order_id": "ORD-101"}}},
                {"text": "Your order is out for delivery."},
            ]
        )
        agent = worker.BrainAgent(
            brain,
            publisher,
            max_call_seconds=300,
            max_tts_characters=2500,
            call_started_at=worker.time.monotonic(),
        )
        context = ChatContext()
        context.add_message(role="user", content="Where is my order ORD-101?")
        assert [text async for text in agent.llm_node(context, [], {})]
        assert brain.state.candidate_id == "ORD-101"
        assert brain.state.confirmed_id is None
        room.message({"type": "text_input", "text": "yes"})

        def end_after_answer(event):
            if event["event_type"] == "state_changed" and event["data"]["state"] == "LISTENING":
                if brain.state.confirmed_id:
                    room.message({"type": "end_call"})

        room.on_publish = end_after_answer
        try:
            await worker._run_text_mode(
                FakeCtx(room),
                publisher,
                room.name,
                1,
                brain,
                messages=messages,
                fallback={"kind": "stt", "from_provider": "sarvam_stt", "to_provider": "text_mode"},
            )
        finally:
            messages.close()
        assert brain.state.confirmed_id == "ORD-101"
        assert brain.state.verified is False
        assert brain.state.turn_count == 2
        assert any(
            e["event_type"] == "tool_called" and e["data"]["tool_name"] == "get_order_details"
            for e in room.events
        )

    asyncio.run(check())


def test_close_event_does_not_advertise_text_until_close_task_finishes(offline, monkeypatch):
    cleanup_done = []

    def create_session(**kwargs):
        session = offline.create_session(**kwargs)

        async def close():
            session.closed += 1
            session.emit("close", SimpleNamespace())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            cleanup_done.append(True)

        session.aclose = close

        def start(s):
            s.emit(
                "error",
                SimpleNamespace(
                    error=SimpleNamespace(recoverable=False),
                    source=s.tts,
                ),
            )

        session.on_start = start
        return session

    monkeypatch.setattr(worker, "AgentSession", create_session)

    def ready(event):
        if event["event_type"] == "provider_failover":
            assert cleanup_done == [True]
            offline.room.message({"type": "end_call"})

    offline.room.on_publish = ready
    asyncio.run(worker.entrypoint(offline.ctx))
    assert cleanup_done == [True]
    assert_finalized(offline)


def test_text_provider_failure_is_explicit_without_mock_success(offline, caplog):
    offline.brain.fail = True
    offline.ctx.job.metadata = json.dumps({"mode": "text"})
    offline.ctx.on_connect = lambda: offline.room.message({"type": "text_input", "text": "hello"})
    offline.room.on_publish = lambda e: (
        offline.room.message({"type": "end_call"})
        if e["event_type"] == "state_changed"
        and e["data"]["state"] == "LISTENING"
        and offline.brain.seen
        else None
    )
    asyncio.run(worker.entrypoint(offline.ctx))
    assert any(
        e["event_type"] == "error" and e["data"]["code"] == "TEXT_MODE_TURN_FAILED"
        for e in offline.room.events
    )
    assert not any(
        e["event_type"] == "transcript_turn" and e["data"]["text"] == "The support team can help."
        for e in offline.room.events
    )
    assert "secret-provider-key-must-not-appear" not in caplog.text
    assert_finalized(offline)


def test_cleanup_failure_finalizes_without_unsafe_text_handover(offline, monkeypatch, caplog):
    def create_session(**kwargs):
        session = offline.create_session(**kwargs)

        async def close():
            session.closed += 1
            session.emit("close", SimpleNamespace())
            raise RuntimeError("secret-close-error")

        session.aclose = close

        def start(s):
            s.emit(
                "error",
                SimpleNamespace(
                    error=SimpleNamespace(recoverable=False),
                    source=s.tts,
                ),
            )

        session.on_start = start
        return session

    monkeypatch.setattr(worker, "AgentSession", create_session)
    asyncio.run(worker.entrypoint(offline.ctx))
    assert not any(offline.sessions[0].listeners.values())
    assert not any(e["event_type"] == "provider_failover" for e in offline.room.events)
    assert "secret-close-error" not in caplog.text
    assert_finalized(offline)
