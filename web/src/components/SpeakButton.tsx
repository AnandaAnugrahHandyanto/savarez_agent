import { useRef, useState } from "react";
import { Volume2, Square, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface Props {
  text: string;
  provider?: string;  // override the configured TTS provider for this call
  voice?: string;     // override the configured voice for this call
  label?: string;     // button label; if omitted, just shows the icon
  size?: "sm" | "default" | "lg" | "icon";
  variant?: "default" | "ghost" | "outline" | "secondary";
  onError?: (err: string) => void;
}

export function SpeakButton({
  text,
  provider,
  voice,
  label,
  size = "sm",
  variant = "ghost",
  onError,
}: Props) {
  const [state, setState] = useState<"idle" | "loading" | "playing">("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);

  const cleanup = () => {
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
    audioRef.current = null;
    setState("idle");
  };

  const stop = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    cleanup();
  };

  const play = async () => {
    if (state !== "idle") {
      stop();
      return;
    }
    if (!text.trim()) return;
    setState("loading");
    try {
      const blob = await api.speak({ text, provider, voice });
      const url = URL.createObjectURL(blob);
      urlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = cleanup;
      audio.onerror = () => {
        onError?.("Audio playback failed");
        cleanup();
      };
      await audio.play();
      setState("playing");
    } catch (err) {
      onError?.(err instanceof Error ? err.message : String(err));
      cleanup();
    }
  };

  const Icon =
    state === "loading" ? Loader2 : state === "playing" ? Square : Volume2;

  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      onClick={play}
      disabled={state === "loading"}
      title={state === "playing" ? "Stop" : "Test voice"}
      aria-label={state === "playing" ? "Stop" : "Test voice"}
    >
      <Icon className={`h-3.5 w-3.5 ${state === "loading" ? "animate-spin" : ""}`} />
      {label && <span className="ml-1.5">{label}</span>}
    </Button>
  );
}
