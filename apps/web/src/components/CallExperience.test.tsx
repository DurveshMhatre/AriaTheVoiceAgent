import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LiveKitTransport } from "@/lib/call/livekitTransport";
import type { TransportStatus } from "@/lib/call/transport";
import CallExperience from "./CallExperience";

describe("CallExperience with FakeTransport", () => {
  it("walks the text call through live and post-call states with transcript and summary", async () => {
    render(<CallExperience email="evaluator@example.test" />);
    fireEvent.click(screen.getByRole("button", { name: "Run scripted demo" }));
    await screen.findByText("Listening");
    fireEvent.change(screen.getByLabelText("Message Aria"), { target: { value: "Where is ORD-101?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText(/out for delivery/i);
    fireEvent.click(screen.getByRole("button", { name: "End call" }));
    await screen.findByRole("heading", { name: "Call summary" });
    expect(screen.getByText("This scripted demo call ended.")).toBeInTheDocument();
  });
  it("shows a connection error rather than Listening when the agent disappears", async () => {
    let notify: (status: TransportStatus, detail?: string) => void = () => undefined;
    const statusSpy = vi.spyOn(LiveKitTransport.prototype, "onStatus").mockImplementation((callback) => { notify = callback; return () => true; });
    let emit: Parameters<LiveKitTransport["onEvent"]>[0] = () => undefined;
    const eventSpy = vi.spyOn(LiveKitTransport.prototype, "onEvent").mockImplementation((callback) => { emit = callback; return () => true; });
    const connectSpy = vi.spyOn(LiveKitTransport.prototype, "connect").mockImplementation(async () => {
      emit({ schema_version: 1, event_id: "listening", call_id: "call-test", tenant_id: "aura", event_type: "state_changed", occurred_at: new Date().toISOString(), sequence: 1, data: { state: "LISTENING" } });
      notify("connected"); notify("agent_active");
      return { call_id: "call-test", room_name: "room-test", server_url: "wss://fake.invalid", participant_token: "fake", expires_in_seconds: 600, voice_mode: "text", fallback_reason: null, max_call_seconds: 300 };
    });
    try {
      render(<CallExperience email="evaluator@example.test" />);
      fireEvent.click(screen.getByRole("button", { name: /^Text$/ }));
      fireEvent.click(screen.getByRole("button", { name: "Start call" }));
      await screen.findByText("Listening");
      act(() => notify("error", "CONNECTION_FAILED"));
      expect(screen.getByRole("alert")).toHaveTextContent("The call connection was interrupted.");
      expect(screen.queryByText("Listening")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Start call" })).toBeEnabled();
    } finally {
      statusSpy.mockRestore(); eventSpy.mockRestore(); connectSpy.mockRestore();
    }
  });
  it("renders notices, orders, and keyboard-operable controls", async () => {
    render(<CallExperience email="evaluator@example.test" />);
    expect(screen.getByText(/calls are transcribed/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Voice$/ })).toHaveClass("selected");
    expect(screen.getByRole("heading", { name: "Test Orders" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Where is ORD-101?" })).toBeEnabled();
    await waitFor(() => expect(screen.getByRole("button", { name: "Start call" })).toBeEnabled());
  });
});
