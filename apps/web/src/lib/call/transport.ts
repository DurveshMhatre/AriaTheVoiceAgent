import type { CallEvent, ClientMessage, TokenResponse } from "./protocol";

export type TransportStatus = "connecting" | "token_received" | "connected" | "reconnecting" | "reconnected" | "disconnected" | "agent_active" | "error";
export type CallTransport = {
  connect(mode: "voice" | "text"): Promise<TokenResponse | null>;
  disconnect(): Promise<void>;
  send(message: ClientMessage): Promise<void>;
  onEvent(callback: (event: CallEvent) => void): () => void;
  onStatus(callback: (status: TransportStatus, detail?: string) => void): () => void;
  setMic(enabled: boolean): Promise<void>;
};
