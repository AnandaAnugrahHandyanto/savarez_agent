import { useEffect, useRef, useState } from "react";
import { Mic, MicOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

type MicState = "idle" | "recording" | "transcribing";

interface Props {
  onTranscript: (text: string) => void;
  onError?: (msg: string) => void;
  size?: "sm" | "default" | "lg" | "icon";
  variant?: "default" | "ghost" | "outline" | "secondary";
  label?: string;
}

export function MicButton({
  onTranscript,
  onError,
  size = "sm",
  variant = "ghost",
  label,
}: Props) {
  const [state, setState] = useState<MicState>("idle");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const cleanupStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    recorderRef.current = null;
    chunksRef.current = [];
  };

  useEffect(() => cleanupStream, []);

  const start = async () => {
    if (state !== "idle") return;
    if (!navigator.mediaDevices?.getUserMedia) {
      onError?.("Microphone API not available in this browser");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType =
        MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "";
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        cleanupStream();
        if (blob.size === 0) {
          setState("idle");
          onError?.("No audio captured");
          return;
        }
        setState("transcribing");
        try {
          const token = window.__HERMES_SESSION_TOKEN__;
          const fd = new FormData();
          // Filename matters for the backend's extension fallback.
          const ext = blob.type.includes("webm") ? "webm" : "wav";
          fd.append("audio", blob, `recording.${ext}`);
          const headers: Record<string, string> = {};
          if (token) headers["Authorization"] = `Bearer ${token}`;
          const res = await fetch("/api/voice/transcribe", {
            method: "POST",
            headers,
            body: fd,
          });
          if (!res.ok) {
            const txt = await res.text().catch(() => res.statusText);
            throw new Error(`${res.status}: ${txt}`);
          }
          const data: { transcript: string } = await res.json();
          onTranscript(data.transcript || "");
        } catch (err) {
          onError?.(err instanceof Error ? err.message : String(err));
        } finally {
          setState("idle");
        }
      };
      recorder.start();
      setState("recording");
    } catch (err) {
      cleanupStream();
      const msg = err instanceof Error ? err.message : String(err);
      onError?.(`Mic permission denied or unavailable: ${msg}`);
      setState("idle");
    }
  };

  const stop = () => {
    if (recorderRef.current && state === "recording") {
      recorderRef.current.stop();
    }
  };

  const handleClick = () => {
    if (state === "idle") start();
    else if (state === "recording") stop();
  };

  const Icon =
    state === "transcribing" ? Loader2 : state === "recording" ? MicOff : Mic;
  const title =
    state === "recording"
      ? "Stop recording"
      : state === "transcribing"
      ? "Transcribing…"
      : "Record voice";

  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      onClick={handleClick}
      disabled={state === "transcribing"}
      title={title}
      aria-label={title}
      className={state === "recording" ? "text-destructive" : undefined}
    >
      <Icon
        className={`h-3.5 w-3.5 ${state === "transcribing" ? "animate-spin" : ""} ${
          state === "recording" ? "animate-pulse" : ""
        }`}
      />
      {label && <span className="ml-1.5">{label}</span>}
    </Button>
  );
}
