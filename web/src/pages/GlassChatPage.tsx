import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronRight,
  History,
  Image as ImageIcon,
  Moon,
  Paperclip,
  Plus,
  Send,
  Settings2,
  Sparkles,
  Sun,
  Type,
  Upload,
  MessageSquareText,
} from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type ThemeMode = "dark" | "light";
type BubbleStyle = "glass" | "soft" | "solid";
type FontSize = "small" | "medium" | "large";
type MessageSpacing = "compact" | "balanced" | "airy";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  note?: string;
  typing?: boolean;
};

const SAMPLE_CHATS = [
  { title: "Glass UI ideas", time: "2 min ago", active: true },
  { title: "Token setup check", time: "18 min ago", active: false },
  { title: "Deal Finder review", time: "Today", active: false },
  { title: "Railway build logs", time: "Yesterday", active: false },
];

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: "welcome",
    role: "assistant",
    text:
      "I can help you make this page feel clean, calm, and original — like polished glass sitting over a deep night sky.",
    note: "Ready to answer questions and show how the layout works.",
  },
  {
    id: "user-1",
    role: "user",
    text: "I want a page that looks modern, but still easy for me to use.",
  },
  {
    id: "assistant-2",
    role: "assistant",
    text:
      "Perfect. We’ll keep the left rail for recent sessions, the center stage for the conversation, and the right rail for quick controls.",
  },
];

const THEME_PRESETS: Record<
  ThemeMode,
  {
    page: string;
    glow: string;
    panel: string;
    panelAlt: string;
    border: string;
    text: string;
    muted: string;
    accent: string;
    accentSoft: string;
    chatUser: string;
    chatAssistant: string;
    chip: string;
    shadow: string;
  }
> = {
  dark: {
    page: "linear-gradient(180deg, #07101c 0%, #0b1526 42%, #070d16 100%)",
    glow: "radial-gradient(circle at 15% 12%, rgba(142, 199, 255, 0.18), transparent 30%), radial-gradient(circle at 85% 10%, rgba(157, 124, 255, 0.18), transparent 26%), radial-gradient(circle at 65% 88%, rgba(83, 220, 197, 0.12), transparent 28%)",
    panel: "rgba(10, 16, 28, 0.62)",
    panelAlt: "rgba(255, 255, 255, 0.05)",
    border: "rgba(255, 255, 255, 0.12)",
    text: "#f3f7ff",
    muted: "rgba(243, 247, 255, 0.68)",
    accent: "#9ed0ff",
    accentSoft: "rgba(158, 208, 255, 0.16)",
    chatUser: "rgba(158, 208, 255, 0.16)",
    chatAssistant: "rgba(255, 255, 255, 0.08)",
    chip: "rgba(255, 255, 255, 0.07)",
    shadow: "0 30px 90px rgba(0, 0, 0, 0.42)",
  },
  light: {
    page: "linear-gradient(180deg, #edf3fb 0%, #f8fbff 44%, #e9eef8 100%)",
    glow: "radial-gradient(circle at 16% 10%, rgba(22, 104, 255, 0.12), transparent 28%), radial-gradient(circle at 82% 14%, rgba(122, 90, 255, 0.12), transparent 24%), radial-gradient(circle at 72% 86%, rgba(83, 220, 197, 0.11), transparent 26%)",
    panel: "rgba(255, 255, 255, 0.66)",
    panelAlt: "rgba(255, 255, 255, 0.78)",
    border: "rgba(15, 23, 42, 0.08)",
    text: "#08111d",
    muted: "rgba(8, 17, 29, 0.62)",
    accent: "#1668ff",
    accentSoft: "rgba(22, 104, 255, 0.10)",
    chatUser: "rgba(22, 104, 255, 0.10)",
    chatAssistant: "rgba(255, 255, 255, 0.74)",
    chip: "rgba(8, 17, 29, 0.05)",
    shadow: "0 28px 80px rgba(15, 23, 42, 0.12)",
  },
};

const FONT_SIZES: Record<FontSize, string> = {
  small: "0.94rem",
  medium: "1rem",
  large: "1.08rem",
};

const SPACING: Record<MessageSpacing, { gap: string; padding: string }> = {
  compact: { gap: "0.6rem", padding: "0.82rem 1rem" },
  balanced: { gap: "0.9rem", padding: "0.95rem 1.08rem" },
  airy: { gap: "1.2rem", padding: "1.08rem 1.18rem" },
};

const BUBBLES: Record<BubbleStyle, string> = {
  glass:
    "backdrop-blur-xl border border-border/60 bg-background-base/25 shadow-[inset_0_1px_0_rgba(255,255,255,0.16)]",
  soft:
    "border border-border/55 bg-background-base/18 shadow-[0_12px_44px_rgba(3,11,22,0.16)]",
  solid: "border border-border/30 bg-background-base/12 shadow-none",
};

function makeReply(prompt: string) {
  const lower = prompt.toLowerCase();
  if (lower.includes("glass")) {
    return "I’d use frosted panels, soft blur, rounded corners, and just one strong accent color so it feels calm instead of busy.";
  }
  if (lower.includes("mobile")) {
    return "On phones, I’d stack the panels so the page still feels easy to read and tap.";
  }
  if (lower.includes("settings")) {
    return "The settings should stay simple: theme, font size, bubble style, and spacing — enough to feel customizable without getting confusing.";
  }
  return "That sounds good. We can make it look polished first, then connect the real chat later.";
}

export default function GlassChatPage() {
  const [themeMode, setThemeMode] = useState<ThemeMode>("dark");
  const [bubbleStyle, setBubbleStyle] = useState<BubbleStyle>("glass");
  const [fontSize, setFontSize] = useState<FontSize>("medium");
  const [spacing, setSpacing] = useState<MessageSpacing>("balanced");
  const [draft, setDraft] = useState(
    "Can you make the glass look softer, calmer, and more like our own brand?",
  );
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [selectedChat, setSelectedChat] = useState(0);
  const [isTyping, setIsTyping] = useState(false);
  const typingTimer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (typingTimer.current) {
        window.clearTimeout(typingTimer.current);
      }
    };
  }, []);

  const palette = THEME_PRESETS[themeMode];
  const layout = SPACING[spacing];

  const rootStyle = useMemo(
    () =>
      ({
        "--glass-page": palette.page,
        "--glass-glow": palette.glow,
        "--glass-panel": palette.panel,
        "--glass-panel-alt": palette.panelAlt,
        "--glass-border": palette.border,
        "--glass-text": palette.text,
        "--glass-muted": palette.muted,
        "--glass-accent": palette.accent,
        "--glass-accent-soft": palette.accentSoft,
        "--glass-chat-user": palette.chatUser,
        "--glass-chat-assistant": palette.chatAssistant,
        "--glass-chip": palette.chip,
        "--glass-shadow": palette.shadow,
        "--glass-font-size": FONT_SIZES[fontSize],
        "--glass-gap": layout.gap,
        "--glass-padding": layout.padding,
      }) as React.CSSProperties,
    [fontSize, layout.gap, layout.padding, palette],
  );

  const sendMessage = () => {
    const text = draft.trim();
    if (!text || isTyping) return;

    if (typingTimer.current) {
      window.clearTimeout(typingTimer.current);
    }

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text,
    };
    const typingMsg: ChatMessage = {
      id: "typing",
      role: "assistant",
      text: "",
      typing: true,
    };

    setMessages((prev) => [...prev, userMsg, typingMsg]);
    setDraft("");
    setIsTyping(true);

    typingTimer.current = window.setTimeout(() => {
      setMessages((prev) => {
        const withoutTyping = prev.filter((msg) => !msg.typing);
        return [
          ...withoutTyping,
          {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            text: makeReply(text),
            note: "Preview reply",
          },
        ];
      });
      setIsTyping(false);
    }, 1100);
  };

  const resetSettings = () => {
    setThemeMode("dark");
    setBubbleStyle("glass");
    setFontSize("medium");
    setSpacing("balanced");
  };

  return (
    <div
      className={cn(
        "relative isolate overflow-hidden rounded-[32px] border",
        "min-h-[calc(100dvh-1.5rem)] p-3 sm:p-4 lg:p-5",
      )}
      style={{
        background: "var(--glass-page)",
        color: "var(--glass-text)",
        borderColor: "var(--glass-border)",
        boxShadow: "var(--glass-shadow)",
        ...rootStyle,
      }}
    >
      <div className="pointer-events-none absolute inset-0" style={{ background: "var(--glass-glow)" }} />

      <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-white/10 to-transparent" />

      <header
        className={cn(
          "relative z-10 mb-4 flex flex-wrap items-center justify-between gap-3",
          "rounded-[28px] border px-4 py-3 backdrop-blur-2xl",
        )}
        style={{
          background: "var(--glass-panel)",
          borderColor: "var(--glass-border)",
        }}
      >
        <div className="flex min-w-0 items-center gap-3">
          <div
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[16px]"
            style={{ background: "var(--glass-accent-soft)", color: "var(--glass-accent)" }}
          >
            <Sparkles className="h-5 w-5" />
          </div>

          <div className="min-w-0">
            <div className="text-xs uppercase tracking-[0.22em]" style={{ color: "var(--glass-muted)" }}>
              Hermes Chat
            </div>
            <div className="truncate text-sm font-medium" style={{ color: "var(--glass-text)" }}>
              Glassy chat page preview
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div
            className="hidden items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium md:flex"
            style={{ background: "var(--glass-panel-alt)", borderColor: "var(--glass-border)", color: "var(--glass-muted)" }}
          >
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Live preview
          </div>

          <Button
            ghost
            className="rounded-full border px-4 py-2 text-xs font-medium normal-case"
            onClick={() => setThemeMode((prev) => (prev === "dark" ? "light" : "dark"))}
            style={{
              background: "var(--glass-panel-alt)",
              borderColor: "var(--glass-border)",
              color: "var(--glass-text)",
            }}
          >
            {themeMode === "dark" ? <Sun className="mr-2 h-4 w-4" /> : <Moon className="mr-2 h-4 w-4" />}
            {themeMode === "dark" ? "Light mode" : "Dark mode"}
          </Button>

          <div
            className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full border"
            style={{ background: "var(--glass-panel-alt)", borderColor: "var(--glass-border)" }}
            aria-label="Profile picture"
            title="Profile picture"
          >
            <span className="text-xs font-semibold" style={{ color: "var(--glass-accent)" }}>
              HG
            </span>
          </div>
        </div>
      </header>

      <main className="relative z-10 grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)_330px]">
        <aside
          className="rounded-[30px] border p-3 backdrop-blur-2xl"
          style={{ background: "var(--glass-panel)", borderColor: "var(--glass-border)" }}
        >
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <div className="text-xs uppercase tracking-[0.2em]" style={{ color: "var(--glass-muted)" }}>
                History
              </div>
              <h2 className="text-base font-semibold" style={{ color: "var(--glass-text)" }}>
                Old chats
              </h2>
            </div>
            <Button
              ghost
              size="icon"
              className="h-10 w-10 rounded-full border"
              style={{ background: "var(--glass-panel-alt)", borderColor: "var(--glass-border)" }}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>

          <div className="space-y-2">
            {SAMPLE_CHATS.map((chat, index) => (
              <button
                key={chat.title}
                type="button"
                onClick={() => setSelectedChat(index)}
                className={cn(
                  "w-full rounded-[22px] border p-3 text-left transition-transform hover:-translate-y-0.5",
                  chat.active || selectedChat === index ? "scale-[1.01]" : "opacity-90",
                )}
                style={{
                  background:
                    chat.active || selectedChat === index
                      ? "var(--glass-accent-soft)"
                      : "var(--glass-panel-alt)",
                  borderColor: chat.active || selectedChat === index ? "var(--glass-border)" : "transparent",
                }}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <History className="h-4 w-4 shrink-0" style={{ color: "var(--glass-accent)" }} />
                    <div className="truncate text-sm font-semibold" style={{ color: "var(--glass-text)" }}>
                      {chat.title}
                    </div>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0" style={{ color: "var(--glass-muted)" }} />
                </div>
                <div className="mt-2 text-xs" style={{ color: "var(--glass-muted)" }}>
                  {chat.time}
                </div>
              </button>
            ))}
          </div>

          <div
            className="mt-4 rounded-[24px] border p-3"
            style={{ background: "var(--glass-panel-alt)", borderColor: "var(--glass-border)" }}
          >
            <div className="flex items-center gap-2 text-sm font-medium" style={{ color: "var(--glass-text)" }}>
              <MessageSquareText className="h-4 w-4" style={{ color: "var(--glass-accent)" }} />
              Layout notes
            </div>
            <ul className="mt-3 space-y-2 text-sm" style={{ color: "var(--glass-muted)" }}>
              <li>• one clear conversation stage</li>
              <li>• a session rail for recent history</li>
              <li>• a control rail for theme and spacing</li>
            </ul>
          </div>
        </aside>

        <section
          className="min-w-0 rounded-[34px] border p-3 backdrop-blur-2xl"
          style={{ background: "var(--glass-panel)", borderColor: "var(--glass-border)" }}
        >
          <div
            className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-[26px] border px-4 py-3"
            style={{ background: "var(--glass-panel-alt)", borderColor: "var(--glass-border)" }}
          >
            <div className="min-w-0">
              <div className="text-xs uppercase tracking-[0.2em]" style={{ color: "var(--glass-muted)" }}>
                Conversation deck
              </div>
              <h1 className="truncate text-lg font-semibold sm:text-xl" style={{ color: "var(--glass-text)" }}>
                Hermes answers in this space
              </h1>
            </div>

            <div className="flex items-center gap-2">
              <div
                className="rounded-full border px-3 py-2 text-xs font-medium"
                style={{ background: "var(--glass-chip)", borderColor: "var(--glass-border)", color: "var(--glass-muted)" }}
              >
                <span className="mr-2 inline-block h-2 w-2 rounded-full bg-emerald-400 align-middle" />
                online
              </div>
              <div
                className="rounded-full border px-3 py-2 text-xs font-medium"
                style={{ background: "var(--glass-chip)", borderColor: "var(--glass-border)", color: "var(--glass-muted)" }}
              >
                {themeMode === "dark" ? "night glass" : "day glass"}
              </div>
            </div>
          </div>

          <div className="space-y-[var(--glass-gap)] rounded-[30px] border p-3" style={{ background: "var(--glass-panel-alt)", borderColor: "var(--glass-border)" }}>
            {messages.map((message) => {
              const bubbleBase = cn(
                "max-w-[92%] rounded-[28px] border px-4 py-3 sm:max-w-[84%]",
                BUBBLES[bubbleStyle],
              );

              return (
                <div
                  key={message.id}
                  className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}
                >
                  <div
                    className={bubbleBase}
                    style={{
                      background:
                        message.role === "user"
                          ? "var(--glass-chat-user)"
                          : message.typing
                            ? "var(--glass-chat-assistant)"
                            : "var(--glass-chat-assistant)",
                      borderColor: "var(--glass-border)",
                      fontSize: "var(--glass-font-size)",
                      color: "var(--glass-text)",
                      padding: "var(--glass-padding)",
                    }}
                  >
                    {message.typing ? (
                      <div className="flex items-center gap-2 py-1">
                        <span className="inline-flex items-center gap-1.5">
                          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-current/45" />
                          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-current/35 [animation-delay:120ms]" />
                          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-current/25 [animation-delay:240ms]" />
                        </span>
                        <span className="text-sm" style={{ color: "var(--glass-muted)" }}>
                          Hermes is typing…
                        </span>
                      </div>
                    ) : (
                      <>
                        <p className="leading-relaxed text-wrap pretty">{message.text}</p>
                        {message.note && (
                          <div className="mt-2 text-xs uppercase tracking-[0.18em]" style={{ color: "var(--glass-muted)" }}>
                            {message.note}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div
            className="mt-3 rounded-[30px] border p-3 backdrop-blur-2xl"
            style={{ background: "var(--glass-panel-alt)", borderColor: "var(--glass-border)" }}
          >
            <div className="mb-3 flex flex-wrap items-center gap-2 text-xs font-medium" style={{ color: "var(--glass-muted)" }}>
              <span className="inline-flex items-center gap-1 rounded-full border px-3 py-1" style={{ background: "var(--glass-chip)", borderColor: "var(--glass-border)" }}>
                <Paperclip className="h-3.5 w-3.5" />
                files
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border px-3 py-1" style={{ background: "var(--glass-chip)", borderColor: "var(--glass-border)" }}>
                <ImageIcon className="h-3.5 w-3.5" />
                images
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border px-3 py-1" style={{ background: "var(--glass-chip)", borderColor: "var(--glass-border)" }}>
                <Upload className="h-3.5 w-3.5" />
                upload
              </span>
            </div>

            <div
              className="flex flex-col gap-3 rounded-[28px] border p-3 sm:flex-row sm:items-end"
              style={{ background: "var(--glass-panel)", borderColor: "var(--glass-border)" }}
            >
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={3}
                className="min-h-[92px] w-full resize-none bg-transparent text-sm outline-none placeholder:text-current/40"
                style={{ color: "var(--glass-text)" }}
                placeholder="Type a message…"
              />

              <div className="flex items-center gap-2 sm:flex-col sm:items-stretch">
                <Button
                  ghost
                  className="h-11 rounded-full border px-4 text-xs font-medium normal-case"
                  onClick={() => setDraft("")}
                  style={{
                    background: "var(--glass-panel-alt)",
                    borderColor: "var(--glass-border)",
                    color: "var(--glass-text)",
                  }}
                >
                  Clear
                </Button>

                <Button
                  className="h-11 rounded-full px-5 text-xs font-medium normal-case"
                  onClick={sendMessage}
                  disabled={!draft.trim() || isTyping}
                  style={{
                    background: "var(--glass-accent)",
                    color: themeMode === "dark" ? "#08111d" : "#ffffff",
                  }}
                >
                  <Send className="mr-2 h-4 w-4" />
                  Send
                </Button>
              </div>
            </div>
          </div>
        </section>

        <aside
          className="rounded-[30px] border p-3 backdrop-blur-2xl"
          style={{ background: "var(--glass-panel)", borderColor: "var(--glass-border)" }}
        >
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <div className="text-xs uppercase tracking-[0.2em]" style={{ color: "var(--glass-muted)" }}>
                Settings
              </div>
              <h2 className="text-base font-semibold" style={{ color: "var(--glass-text)" }}>
                Make it yours
              </h2>
            </div>
            <Button
              ghost
              size="icon"
              onClick={resetSettings}
              className="h-10 w-10 rounded-full border"
              style={{ background: "var(--glass-panel-alt)", borderColor: "var(--glass-border)" }}
              aria-label="Reset settings"
            >
              <Settings2 className="h-4 w-4" />
            </Button>
          </div>

          <div className="space-y-3">
            <Card
              className="rounded-[26px] border-0"
              style={{ background: "var(--glass-panel-alt)", borderColor: "var(--glass-border)" }}
            >
              <CardHeader className="border-0 pb-2">
                <CardTitle className="text-sm tracking-[0.18em]">Theme</CardTitle>
              </CardHeader>
              <CardContent className="flex gap-2 pt-0">
                {(["dark", "light"] as ThemeMode[]).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setThemeMode(mode)}
                    className={cn(
                      "flex flex-1 items-center justify-center gap-2 rounded-full border px-3 py-2 text-xs font-medium transition-all",
                      themeMode === mode ? "scale-[1.02]" : "opacity-75",
                    )}
                    style={{
                      background: themeMode === mode ? "var(--glass-accent-soft)" : "transparent",
                      borderColor: "var(--glass-border)",
                      color: "var(--glass-text)",
                    }}
                  >
                    {mode === "dark" ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
                    {mode}
                  </button>
                ))}
              </CardContent>
            </Card>

            <Card className="rounded-[26px] border-0" style={{ background: "var(--glass-panel-alt)" }}>
              <CardHeader className="border-0 pb-2">
                <CardTitle className="text-sm tracking-[0.18em]">Font size</CardTitle>
              </CardHeader>
              <CardContent className="flex gap-2 pt-0">
                {(["small", "medium", "large"] as FontSize[]).map((size) => (
                  <button
                    key={size}
                    type="button"
                    onClick={() => setFontSize(size)}
                    className={cn(
                      "flex flex-1 items-center justify-center rounded-full border px-3 py-2 text-xs font-medium capitalize",
                      fontSize === size ? "scale-[1.02]" : "opacity-75",
                    )}
                    style={{
                      background: fontSize === size ? "var(--glass-accent-soft)" : "transparent",
                      borderColor: "var(--glass-border)",
                      color: "var(--glass-text)",
                    }}
                  >
                    <Type className="mr-2 h-3.5 w-3.5" />
                    {size}
                  </button>
                ))}
              </CardContent>
            </Card>

            <Card className="rounded-[26px] border-0" style={{ background: "var(--glass-panel-alt)" }}>
              <CardHeader className="border-0 pb-2">
                <CardTitle className="text-sm tracking-[0.18em]">Bubble style</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2 pt-0">
                {(["glass", "soft", "solid"] as BubbleStyle[]).map((styleName) => (
                  <button
                    key={styleName}
                    type="button"
                    onClick={() => setBubbleStyle(styleName)}
                    className={cn(
                      "flex items-center justify-between rounded-[20px] border px-3 py-2 text-xs font-medium capitalize",
                      bubbleStyle === styleName ? "scale-[1.01]" : "opacity-75",
                    )}
                    style={{
                      background: bubbleStyle === styleName ? "var(--glass-accent-soft)" : "transparent",
                      borderColor: "var(--glass-border)",
                      color: "var(--glass-text)",
                    }}
                  >
                    <span>{styleName}</span>
                    <span className="text-[0.65rem] uppercase tracking-[0.18em]" style={{ color: "var(--glass-muted)" }}>
                      preview
                    </span>
                  </button>
                ))}
              </CardContent>
            </Card>

            <Card className="rounded-[26px] border-0" style={{ background: "var(--glass-panel-alt)" }}>
              <CardHeader className="border-0 pb-2">
                <CardTitle className="text-sm tracking-[0.18em]">Spacing</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2 pt-0">
                {(["compact", "balanced", "airy"] as MessageSpacing[]).map((step) => (
                  <button
                    key={step}
                    type="button"
                    onClick={() => setSpacing(step)}
                    className={cn(
                      "flex items-center justify-between rounded-[20px] border px-3 py-2 text-xs font-medium capitalize",
                      spacing === step ? "scale-[1.01]" : "opacity-75",
                    )}
                    style={{
                      background: spacing === step ? "var(--glass-accent-soft)" : "transparent",
                      borderColor: "var(--glass-border)",
                      color: "var(--glass-text)",
                    }}
                  >
                    <span>{step}</span>
                    <span className="text-[0.65rem] uppercase tracking-[0.18em]" style={{ color: "var(--glass-muted)" }}>
                      spacing
                    </span>
                  </button>
                ))}
              </CardContent>
            </Card>
          </div>
        </aside>
      </main>
    </div>
  );
}
