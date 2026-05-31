import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Typography } from "@nous-research/ui/ui/components/typography/index";
import { api, type VoiceToolRequest } from "@/lib/api";

type CallStatus = "idle" | "requesting" | "connecting" | "live" | "ending" | "error";

type LogKind = "system" | "user" | "rolly" | "tool" | "error";

interface LogEntry {
  id: string;
  kind: LogKind;
  text: string;
}

function logId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function eventText(event: unknown): string | null {
  if (!event || typeof event !== "object") return null;
  const obj = event as Record<string, unknown>;
  const direct = obj.transcript ?? obj.text ?? obj.delta;
  return typeof direct === "string" && direct.trim() ? direct.trim() : null;
}

export default function VoiceCallPage() {
  const [status, setStatus] = useState<CallStatus>("idle");
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([
    {
      id: logId(),
      kind: "system",
      text: "Prototype: browser WebRTC to realtime voice, with backend tool bridge for research.",
    },
  ]);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const dataRef = useRef<RTCDataChannel | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const callSeqRef = useRef(0);

  const addLog = useCallback((kind: LogKind, text: string) => {
    setLogs((prev) => [...prev.slice(-80), { id: logId(), kind, text }]);
  }, []);

  const stopCall = useCallback(() => {
    callSeqRef.current += 1;
    setStatus((current) => (current === "idle" ? current : "ending"));
    if (dataRef.current) {
      dataRef.current.onmessage = null;
      dataRef.current.onerror = null;
      dataRef.current.onopen = null;
    }
    dataRef.current?.close();
    peerRef.current?.close();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    if (audioRef.current?.srcObject instanceof MediaStream) {
      audioRef.current.srcObject.getTracks().forEach((track) => track.stop());
      audioRef.current.srcObject = null;
    }
    dataRef.current = null;
    peerRef.current = null;
    streamRef.current = null;
    setMuted(false);
    setStatus("idle");
    addLog("system", "Call ended; microphone released.");
  }, [addLog]);

  const sendRealtimeEvent = useCallback((payload: Record<string, unknown>) => {
    const channel = dataRef.current;
    if (!channel || channel.readyState !== "open") return;
    channel.send(JSON.stringify(payload));
  }, []);

  const handleToolCall = useCallback(
    async (event: Record<string, unknown>) => {
      const name = typeof event.name === "string" ? event.name : "";
      const callId = typeof event.call_id === "string" ? event.call_id : "";
      const rawArgs = typeof event.arguments === "string" ? event.arguments : "{}";
      if (!name || !callId) return;

      let args: Record<string, unknown> = {};
      try {
        args = JSON.parse(rawArgs) as Record<string, unknown>;
      } catch {
        args = { raw: rawArgs };
      }

      addLog("tool", `Running ${name}…`);
      try {
        const result = await api.runVoiceTool({ name, arguments: args } satisfies VoiceToolRequest);
        const output = result.ok ? result.result : `Tool failed: ${result.error ?? "unknown error"}`;
        addLog(result.ok ? "tool" : "error", output.slice(0, 700));
        sendRealtimeEvent({
          type: "conversation.item.create",
          item: {
            type: "function_call_output",
            call_id: callId,
            output,
          },
        });
        sendRealtimeEvent({ type: "response.create" });
      } catch (exc) {
        const message = exc instanceof Error ? exc.message : String(exc);
        addLog("error", message);
        sendRealtimeEvent({
          type: "conversation.item.create",
          item: {
            type: "function_call_output",
            call_id: callId,
            output: `Tool failed: ${message}`,
          },
        });
        sendRealtimeEvent({ type: "response.create" });
      }
    },
    [addLog, sendRealtimeEvent],
  );

  const handleRealtimeEvent = useCallback(
    (message: MessageEvent<string>) => {
      let event: Record<string, unknown>;
      try {
        event = JSON.parse(message.data) as Record<string, unknown>;
      } catch {
        return;
      }
      const type = typeof event.type === "string" ? event.type : "";

      if (type === "response.function_call_arguments.done") {
        void handleToolCall(event);
        return;
      }
      if (type === "conversation.item.input_audio_transcription.completed") {
        const text = eventText(event);
        if (text) addLog("user", text);
        return;
      }
      if (type === "response.audio_transcript.done" || type === "response.output_text.done") {
        const text = eventText(event);
        if (text) addLog("rolly", text);
        return;
      }
      if (type === "error") {
        const messageText = JSON.stringify(event.error ?? event).slice(0, 700);
        addLog("error", messageText);
      }
    },
    [addLog, handleToolCall],
  );

  const startCall = useCallback(async () => {
    const callSeq = callSeqRef.current + 1;
    callSeqRef.current = callSeq;
    const isCurrentCall = () => callSeqRef.current === callSeq;
    setError(null);
    setStatus("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!isCurrentCall()) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      setStatus("connecting");

      const session = await api.createVoiceSession();
      if (!isCurrentCall()) return;
      const peer = new RTCPeerConnection();
      peerRef.current = peer;
      peer.onconnectionstatechange = () => {
        if (["closed", "disconnected", "failed"].includes(peer.connectionState)) {
          addLog("system", `Connection ${peer.connectionState}.`);
        }
      };

      peer.ontrack = (event) => {
        if (!audioRef.current) return;
        audioRef.current.srcObject = event.streams[0];
      };
      stream.getAudioTracks().forEach((track) => peer.addTrack(track, stream));

      const dataChannel = peer.createDataChannel("oai-events");
      dataRef.current = dataChannel;
      dataChannel.onopen = () => {
        setStatus("live");
        addLog("system", "Live. Talk normally; Rolly can answer by voice and call tools.");
      };
      dataChannel.onmessage = handleRealtimeEvent;
      dataChannel.onerror = () => addLog("error", "Realtime data channel error.");

      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);

      const realtimeUrl = `${session.endpoint}?model=${encodeURIComponent(session.model)}`;
      const sdpResponse = await fetch(realtimeUrl, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.client_secret}`,
          "Content-Type": "application/sdp",
        },
        body: offer.sdp,
      });
      if (!sdpResponse.ok) {
        throw new Error(`${sdpResponse.status}: ${await sdpResponse.text()}`);
      }
      if (!isCurrentCall()) return;
      await peer.setRemoteDescription({ type: "answer", sdp: await sdpResponse.text() });
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : String(exc);
      setError(message);
      setStatus("error");
      addLog("error", message);
      stopCall();
    }
  }, [addLog, handleRealtimeEvent, stopCall]);

  const toggleMute = useCallback(() => {
    const next = !muted;
    streamRef.current?.getAudioTracks().forEach((track) => {
      track.enabled = !next;
    });
    setMuted(next);
  }, [muted]);

  useEffect(() => stopCall, [stopCall]);

  const live = status === "live";
  const busy = status === "requesting" || status === "connecting" || status === "ending";

  return (
    <main className="flex h-full min-h-0 flex-col gap-4 overflow-auto p-4 lg:p-6">
      <audio ref={audioRef} autoPlay />
      <section className="border border-current/20 bg-background-base/70 p-5 text-midground shadow-xl">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <Typography className="font-mondwest text-display text-2xl uppercase tracking-[0.12em]">
              Rolly Voice
            </Typography>
            <p className="mt-2 max-w-2xl text-sm text-text-secondary">
              One-on-one call prototype: browser mic/audio, realtime speech, and a backend bridge for bounded research/tool calls.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!live && !busy ? <Button onClick={startCall}>Start call</Button> : null}
            {live ? <Button onClick={toggleMute}>{muted ? "Unmute" : "Mute"}</Button> : null}
            {live || busy ? <Button onClick={stopCall}>End call</Button> : null}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2 text-xs uppercase tracking-[0.12em] text-text-secondary">
          <span className="border border-current/20 px-2 py-1">Status: {status}</span>
          <span className="border border-current/20 px-2 py-1">Provider: OpenAI Realtime WebRTC</span>
          <span className="border border-current/20 px-2 py-1">Tools: research</span>
        </div>
        {error ? <p className="mt-3 text-sm text-red-300">{error}</p> : null}
      </section>

      <section className="grid min-h-[24rem] gap-4 lg:grid-cols-[1fr_22rem]">
        <div className="min-h-0 border border-current/20 bg-black/30 p-4">
          <Typography className="font-mondwest text-display text-lg uppercase tracking-[0.12em]">
            Transcript + events
          </Typography>
          <div className="mt-3 flex max-h-[60vh] flex-col gap-2 overflow-auto pr-1 text-sm">
            {logs.map((entry) => (
              <div key={entry.id} className="border border-current/10 bg-background-base/50 p-3">
                <div className="mb-1 text-[0.65rem] uppercase tracking-[0.14em] text-text-secondary">
                  {entry.kind}
                </div>
                <div className="whitespace-pre-wrap leading-relaxed">{entry.text}</div>
              </div>
            ))}
          </div>
        </div>
        <aside className="border border-current/20 bg-background-base/50 p-4 text-sm text-text-secondary">
          <Typography className="font-mondwest text-display text-lg uppercase tracking-[0.12em] text-midground">
            Try saying
          </Typography>
          <ul className="mt-3 list-disc space-y-2 pl-4">
            <li>“Rolly, research the best way to test this voice prototype.”</li>
            <li>“Summarize what we’ve decided so far.”</li>
            <li>“Use your research tool and keep the answer brief.”</li>
          </ul>
          <p className="mt-4">
            V1 intentionally avoids Meet/Telegram call plumbing. If this feels good, the production upgrade path is LiveKit.
          </p>
        </aside>
      </section>
    </main>
  );
}
