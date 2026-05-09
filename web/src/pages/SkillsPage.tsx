import { useEffect, useLayoutEffect, useState, useMemo } from "react";
import {
  Package,
  Search,
  Wrench,
  X,
  Cpu,
  Globe,
  Shield,
  Eye,
  Paintbrush,
  Brain,
  Blocks,
  Code,
  Zap,
  Filter,
} from "lucide-react";
import { api } from "@/lib/api";
import type { SkillInfo, ToolsetInfo } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { Toast } from "@/components/Toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { ListItem } from "@nous-research/ui/ui/components/list-item";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Switch } from "@nous-research/ui/ui/components/switch";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { PluginSlot } from "@/plugins";

/* ------------------------------------------------------------------ */
/*  Types & helpers                                                    */
/* ------------------------------------------------------------------ */

const CATEGORY_LABELS: Record<string, string> = {
  mlops: "MLOps",
  "mlops/cloud": "MLOps / Cloud",
  "mlops/evaluation": "MLOps / Evaluation",
  "mlops/inference": "MLOps / Inference",
  "mlops/models": "MLOps / Models",
  "mlops/training": "MLOps / Training",
  "mlops/vector-databases": "MLOps / Vector DBs",
  mcp: "MCP",
  "red-teaming": "Red Teaming",
  ocr: "OCR",
  p5js: "p5.js",
  ai: "AI",
  ux: "UX",
  ui: "UI",
};

function prettyCategory(
  raw: string | null | undefined,
  generalLabel: string,
): string {
  if (!raw) return generalLabel;
  if (CATEGORY_LABELS[raw]) return CATEGORY_LABELS[raw];
  return raw
    .split(/[-_/]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}


const SKILL_DESCRIPTION_JA: Record<string, string> = {
  "claude-code": "Claude Code CLI に実装作業を任せます（機能追加、PR 作成など）。",
  "codex": "OpenAI Codex CLI に実装作業を任せます（機能追加、PR 作成など）。",
  "hermes-agent": "Hermes Agent の設定、拡張、開発に使います。",
  "opencode": "OpenCode CLI に実装作業や PR レビューを任せます。",
  "cloudflare": "Workers、Pages、KV/D1/R2、Workers AI、Tunnel、WAF など Cloudflare 全般を扱います。",
  "agents-sdk": "Cloudflare Workers 上で、状態を持つエージェント、ワークフロー、WebSocket アプリ、MCP サーバー、チャット/音声エージェントを作ります。",
  "cloudflare-email-service": "Cloudflare Email Service で取引メールの送受信、ルーティング、Workers 連携を扱います。",
  "durable-objects": "Cloudflare Durable Objects で状態管理、SQLite ストレージ、アラーム、WebSocket を実装・レビューします。",
  "sandbox-sdk": "安全なコード実行、コードインタープリタ、CI/CD、対話型の開発環境を構築します。",
  "workers-best-practices": "Cloudflare Workers のコードを本番運用向けの作法に沿って作成・レビューします。",
  "wrangler": "Wrangler CLI で Workers、KV、R2、D1、Vectorize、Workers AI などをデプロイ・管理します。",
  "web-perf": "Chrome DevTools MCP で Core Web Vitals と Web 性能を分析します。",
  "architecture-diagram": "ダークテーマのアーキテクチャ図、クラウド構成図、インフラ図を SVG/HTML で作成します。",
  "ascii-art": "pyfiglet、cowsay、boxes、image-to-ascii で ASCII アートを作成します。",
  "ascii-video": "動画や音声を、色付き ASCII の MP4/GIF に変換します。",
  "baoyu-comic": "教育、伝記、チュートリアル向けの知識漫画を作成します。",
  "baoyu-infographic": "情報図や可視化インフォグラフィックを、21 種類の構成と 21 種類のスタイルで作成します。",
  "claude-design": "ランディングページ、資料、プロトタイプなど、単発の HTML デザイン成果物を作成します。",
  "comfyui": "ComfyUI の導入、起動、ワークフロー実行を行い、画像・動画・音声を生成します。",
  "ideation": "制約条件を手がかりに、プロジェクト案を発想します。",
  "design-md": "Google DESIGN.md のトークン仕様ファイルを作成、検証、書き出しします。",
  "excalidraw": "アーキテクチャ、フロー、シーケンスなどの手描き風 Excalidraw JSON 図を作成します。",
  "humanizer": "AI っぽさを取り除き、自然な文章に整えます。",
  "manim-video": "Manim CE で 3Blue1Brown 風の数学・アルゴリズム動画を作成します。",
  "p5js": "p5.js で生成アート、シェーダー、対話型スケッチ、3D スケッチを作ります。",
  "pixel-art": "NES、Game Boy、PICO-8 などの配色でピクセルアートを作ります。",
  "popular-web-designs": "Stripe、Linear、Vercel など実在のデザインシステム風 HTML/CSS を作成します。",
  "pretext": "@chenglou/pretext で ASCII や文字組みを使ったブラウザデモを構築します。",
  "sketch": "比較用の使い捨て HTML モックアップを 2〜3 案作成します。",
  "songwriting-and-ai-music": "作詞の技法と Suno 向け音楽生成プロンプトを扱います。",
  "touchdesigner-mcp": "twozero MCP で TouchDesigner を操作し、リアルタイム映像を構築します。",
  "jupyter-live-kernel": "稼働中の Jupyter カーネルを使い、Python を対話的に探索します。",
  "domain-lifecycle": "ドメインの命名、空き確認、DNS、Cloudflare、メールルーティング、到達性を扱います。",
  "kanban-orchestrator": "Kanban で作業を分解し、適切な専門プロファイルへ回すための手順です。",
  "kanban-worker": "Hermes Kanban ワーカー向けに、落とし穴、引き継ぎ、再試行、例外処理を扱います。",
  "linux-desktop-admin-and-troubleshooting": "Linux デスクトップ/ワークステーションの DNS、HTTPS 信頼、polkit、リモートデスクトップ、端末キー設定を管理・調査します。",
  "self-hosted-service-ops": "LAN 優先のセルフホストサービスを Docker Compose などで運用します。",
  "webhook-subscriptions": "Webhook 購読によるイベント駆動のエージェント実行を扱います。",
  "dogfood": "Web アプリを探索的に QA し、不具合、証拠、報告をまとめます。",
  "himalaya": "Himalaya CLI で IMAP/SMTP メールを端末から扱います。",
  "minecraft-modpack-server": "CurseForge/Modrinth などの Mod 入り Minecraft サーバーを構築・運用します。",
  "pokemon-player": "ヘッドレスエミュレータと RAM 読み取りで Pokemon をプレイします。",
  "codebase-inspection": "pygount でコードベースの行数、言語構成、比率を調査します。",
  "github-auth": "GitHub の HTTPS トークン、SSH キー、gh CLI ログインを設定します。",
  "github-code-review": "PR の差分をレビューし、gh/REST でインラインコメントします。",
  "github-issues": "GitHub Issue の作成、整理、ラベル付け、担当者設定を行います。",
  "github-pr-workflow": "GitHub PR のブランチ作成、コミット、オープン、CI、マージまでを扱います。",
  "github-repo-management": "リポジトリの clone/create/fork、remote、release を管理します。",
  "native-mcp": "MCP クライアントとして stdio/HTTP サーバーに接続し、ツール登録を扱います。",
  "gif-search": "Tenor から curl + jq で GIF を検索・取得します。",
  "heartmula": "HeartMuLa で歌詞とタグから Suno 風の曲を生成します。",
  "songsee": "音声のスペクトログラムや特徴量（mel、chroma、MFCC）を CLI で扱います。",
  "spotify": "Spotify の再生、検索、キュー、プレイリスト、デバイスを管理します。",
  "youtube-content": "YouTube の文字起こしを要約、スレッド、ブログ記事に変換します。",
  "evaluating-llms-harness": "lm-eval-harness で MMLU、GSM8K などの LLM ベンチマークを実行します。",
  "weights-and-biases": "W&B で実験、スイープ、モデル登録、ダッシュボードを管理します。",
  "huggingface-hub": "Hugging Face の hf CLI でモデル/データセットを検索、取得、アップロードします。",
  "llama-cpp": "llama.cpp でローカル GGUF 推論と Hugging Face Hub のモデル探索を扱います。",
  "obliteratus": "diff-in-means による LLM の拒否傾向除去を扱います。",
  "outlines": "Outlines で JSON、正規表現、Pydantic に沿った構造化生成を行います。",
  "serving-llms-vllm": "vLLM で高スループットの LLM 配信、OpenAI API、量子化を扱います。",
  "audiocraft-audio-generation": "AudioCraft/MusicGen/AudioGen でテキストから音楽や効果音を生成します。",
  "segment-anything-model": "SAM で点、矩形、マスクを使ったゼロショット画像セグメンテーションを行います。",
  "dspy": "DSPy で宣言的な LM プログラム、プロンプト最適化、RAG を構築します。",
  "axolotl": "Axolotl の YAML で LoRA、DPO、GRPO などの LLM ファインチューニングを行います。",
  "fine-tuning-with-trl": "TRL で SFT、DPO、PPO、GRPO、報酬モデル作成を行います。",
  "unsloth": "Unsloth で高速な LoRA/QLoRA ファインチューニングを行います。",
  "explicit-memory": "『覚えておいて』『メモして』などの依頼を、明示的なメモとして保存します。",
  "obsidian": "Obsidian vault のノートを読み取り、検索し、新規作成します。",
  "airtable": "Airtable REST API でレコードの CRUD、絞り込み、upsert を行います。",
  "google-workspace": "Gmail、Calendar、Drive、Docs、Sheets を gws CLI や Python で扱います。",
  "linear": "Linear の Issue、プロジェクト、チームを GraphQL/curl で管理します。",
  "maps": "OpenStreetMap/OSRM でジオコーディング、施設検索、経路、タイムゾーンを扱います。",
  "nano-pdf": "nano-pdf CLI で PDF の誤字、本文、タイトルを自然言語で編集します。",
  "notion": "Notion API でページ、データベース、ブロック、検索を扱います。",
  "ocr-and-documents": "PDF やスキャン画像から pymupdf や marker-pdf でテキストを抽出します。",
  "powerpoint": "PowerPoint 資料の作成、読み取り、編集、ノート、テンプレートを扱います。",
  "voice-dictation-apps": "ローカル音声認識とカスタム LLM/API バックエンドを使う GUI 音声入力アプリを評価・設定します。",
  "godmode": "Parseltongue、GODMODE、ULTRAPLINIAN などの LLM jailbreak を扱います。",
  "arxiv": "arXiv 論文をキーワード、著者、カテゴリ、ID で検索します。",
  "blogwatcher": "blogwatcher-cli でブログや RSS/Atom フィードを監視します。",
  "llm-wiki": "Karpathy の LLM Wiki を Markdown 知識ベースとして構築・検索します。",
  "polymarket": "Polymarket のマーケット、価格、板、履歴を照会します。",
  "research-paper-writing": "NeurIPS/ICML/ICLR 向け ML 論文の設計から投稿までを支援します。",
  "openhue": "OpenHue CLI で Philips Hue のライト、シーン、部屋を制御します。",
  "xurl": "xurl CLI で X/Twitter の投稿、検索、DM、メディア、v2 API を扱います。",
  "debugging-hermes-tui-commands": "Hermes TUI の slash command を Python、gateway、Ink UI の経路でデバッグします。",
  "docs-commit-push-workflow": "ドキュメント更新後の確認、差分確認、コミット、プッシュを安全に実行します。",
  "hermes-agent-development": "Hermes Agent 本体の開発、デバッグ、UI ビルド成果物、実行時検証を扱います。",
  "hermes-agent-skill-authoring": "リポジトリ内 SKILL.md の frontmatter、検証、構造を作成します。",
  "node-inspect-debugger": "Node.js を --inspect と Chrome DevTools Protocol CLI でデバッグします。",
  "plan": "実行せず、Markdown の計画を .hermes/plans/ に書く計画モードです。",
  "python-debugpy": "pdb REPL と debugpy リモート（DAP）で Python をデバッグします。",
  "requesting-code-review": "コミット前レビュー、セキュリティ確認、品質ゲート、自動修正を行います。",
  "spike": "実装前に使い捨ての実験でアイデアを検証します。",
  "subagent-driven-development": "delegate_task サブエージェントで、2 段階レビュー付きの実装を行います。",
  "systematic-debugging": "原因理解を先に行う 4 段階の系統的デバッグです。",
  "test-driven-development": "RED-GREEN-REFACTOR に沿ったテスト駆動開発を行います。",
  "vscode-extension-development": "VS Code 拡張機能のビルド、デバッグ、パッケージ化、設定を扱います。",
  "writing-plans": "小さなタスク、対象パス、コード方針を含む実装計画を書きます。",
  "yuanbao": "Yuanbao（元宝）のグループで @mention、情報照会、メンバー照会を行います。",
};
function skillDescription(skill: SkillInfo, locale: string): string {
  if (locale === "ja") return SKILL_DESCRIPTION_JA[skill.name] || skill.description;
  return skill.description;
}

const TOOLSET_ICONS: Record<
  string,
  React.ComponentType<{ className?: string }>
> = {
  computer: Cpu,
  web: Globe,
  security: Shield,
  vision: Eye,
  design: Paintbrush,
  ai: Brain,
  integration: Blocks,
  code: Code,
  automation: Zap,
};

function toolsetIcon(
  name: string,
): React.ComponentType<{ className?: string }> {
  const lower = name.toLowerCase();
  for (const [key, icon] of Object.entries(TOOLSET_ICONS)) {
    if (lower.includes(key)) return icon;
  }
  return Wrench;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [toolsets, setToolsets] = useState<ToolsetInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"skills" | "toolsets">("skills");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [togglingSkills, setTogglingSkills] = useState<Set<string>>(new Set());
  const { toast, showToast } = useToast();
  const { t, locale } = useI18n();
  const { setAfterTitle, setEnd } = usePageHeader();

  useEffect(() => {
    Promise.all([api.getSkills(), api.getToolsets()])
      .then(([s, tsets]) => {
        setSkills(s);
        setToolsets(tsets);
      })
      .catch(() => showToast(t.common.loading, "error"))
      .finally(() => setLoading(false));
  }, []);

  /* ---- Toggle skill ---- */
  const handleToggleSkill = async (skill: SkillInfo) => {
    setTogglingSkills((prev) => new Set(prev).add(skill.name));
    try {
      await api.toggleSkill(skill.name, !skill.enabled);
      setSkills((prev) =>
        prev.map((s) =>
          s.name === skill.name ? { ...s, enabled: !s.enabled } : s,
        ),
      );
      showToast(
        `${skill.name} ${skill.enabled ? t.common.disabled : t.common.enabled}`,
        "success",
      );
    } catch {
      showToast(`${t.common.failedToToggle} ${skill.name}`, "error");
    } finally {
      setTogglingSkills((prev) => {
        const next = new Set(prev);
        next.delete(skill.name);
        return next;
      });
    }
  };

  /* ---- Derived data ---- */
  const lowerSearch = search.toLowerCase();
  const isSearching = search.trim().length > 0;

  const searchMatchedSkills = useMemo(() => {
    if (!isSearching) return [];
    return skills.filter(
      (s) =>
        s.name.toLowerCase().includes(lowerSearch) ||
        s.description.toLowerCase().includes(lowerSearch) ||
        skillDescription(s, locale).toLowerCase().includes(lowerSearch) ||
        (s.category ?? "").toLowerCase().includes(lowerSearch),
    );
  }, [skills, isSearching, lowerSearch, locale]);

  const activeSkills = useMemo(() => {
    if (isSearching) return [];
    if (!activeCategory)
      return [...skills].sort((a, b) => a.name.localeCompare(b.name));
    return skills
      .filter((s) =>
        activeCategory === "__none__"
          ? !s.category
          : s.category === activeCategory,
      )
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [skills, activeCategory, isSearching]);

  const allCategories = useMemo(() => {
    const cats = new Map<string, number>();
    for (const s of skills) {
      const key = s.category || "__none__";
      cats.set(key, (cats.get(key) || 0) + 1);
    }
    return [...cats.entries()]
      .sort((a, b) => {
        if (a[0] === "__none__") return -1;
        if (b[0] === "__none__") return 1;
        return a[0].localeCompare(b[0]);
      })
      .map(([key, count]) => ({
        key,
        name: prettyCategory(key === "__none__" ? null : key, t.common.general),
        count,
      }));
  }, [skills, t]);

  const enabledCount = skills.filter((s) => s.enabled).length;

  useLayoutEffect(() => {
    if (loading) {
      setAfterTitle(null);
      setEnd(null);
      return;
    }
    setAfterTitle(
      <span className="whitespace-nowrap text-xs text-muted-foreground">
        {t.skills.enabledOf
          .replace("{enabled}", String(enabledCount))
          .replace("{total}", String(skills.length))}
      </span>,
    );
    setEnd(
      <div className="relative w-full min-w-0 sm:max-w-xs">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          className="h-8 pl-8 pr-7 text-xs"
          placeholder={t.common.search}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {search && (
          <Button
            ghost
            size="xs"
            className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => setSearch("")}
            aria-label={t.common.clear}
          >
            <X />
          </Button>
        )}
      </div>,
    );
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [enabledCount, loading, search, setAfterTitle, setEnd, skills.length, t]);

  const filteredToolsets = useMemo(() => {
    return toolsets.filter(
      (ts) =>
        !search ||
        ts.name.toLowerCase().includes(lowerSearch) ||
        ts.label.toLowerCase().includes(lowerSearch) ||
        ts.description.toLowerCase().includes(lowerSearch),
    );
  }, [toolsets, search, lowerSearch]);

  /* ---- Loading ---- */
  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="text-2xl text-primary" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PluginSlot name="skills:top" />
      <Toast toast={toast} />

      <div className="flex flex-col sm:flex-row sm:items-start gap-4">
        <aside aria-label={t.skills.title} className="sm:w-56 sm:shrink-0">
          <div className="sm:sticky sm:top-0">
            <div
              className={`
                flex flex-col
                border border-border bg-muted/20
              `}
            >
              <div className="hidden sm:flex items-center gap-2 px-3 py-2 border-b border-border">
                <Filter className="h-3 w-3 text-muted-foreground" />
                <span className="font-mondwest text-[0.65rem] tracking-[0.12em] uppercase text-muted-foreground">
                  {t.skills.filters}
                </span>
              </div>

              <div className="flex sm:flex-col gap-1 overflow-x-auto sm:overflow-x-visible scrollbar-none p-2">
                <PanelItem
                  icon={Package}
                  label={`${t.skills.all} (${skills.length})`}
                  active={view === "skills" && !isSearching}
                  onClick={() => {
                    setView("skills");
                    setActiveCategory(null);
                    setSearch("");
                  }}
                />
                <PanelItem
                  icon={Wrench}
                  label={`${t.skills.toolsets} (${toolsets.length})`}
                  active={view === "toolsets"}
                  onClick={() => {
                    setView("toolsets");
                    setSearch("");
                  }}
                />
              </div>

              {view === "skills" &&
                !isSearching &&
                allCategories.length > 0 && (
                  <div className="hidden sm:flex flex-col border-t border-border">
                    <div className="px-3 pt-2 pb-1 font-mondwest text-[0.6rem] tracking-[0.12em] uppercase text-muted-foreground/70">
                      {t.skills.categories}
                    </div>
                    <div className="flex flex-col p-2 pt-1 gap-px max-h-[calc(100vh-340px)] overflow-y-auto">
                      {allCategories.map(({ key, name, count }) => {
                        const isActive = activeCategory === key;

                        return (
                          <ListItem
                            key={key}
                            active={isActive}
                            onClick={() =>
                              setActiveCategory(isActive ? null : key)
                            }
                            className="rounded-sm px-2 py-1 text-[11px]"
                          >
                            <span className="flex-1 truncate">{name}</span>
                            <span
                              className={`text-[10px] tabular-nums ${
                                isActive
                                  ? "text-foreground/60"
                                  : "text-muted-foreground/50"
                              }`}
                            >
                              {count}
                            </span>
                          </ListItem>
                        );
                      })}
                    </div>
                  </div>
                )}
            </div>
          </div>
        </aside>

        <div className="flex-1 min-w-0">
          {isSearching ? (
            <Card>
              <CardHeader className="py-3 px-4">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Search className="h-4 w-4" />
                    {t.skills.title}
                  </CardTitle>
                  <Badge tone="secondary" className="text-[10px]">
                    {t.skills.resultCount
                      .replace("{count}", String(searchMatchedSkills.length))
                      .replace(
                        "{s}",
                        searchMatchedSkills.length !== 1 ? "s" : "",
                      )}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="px-4 pb-4">
                {searchMatchedSkills.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-8">
                    {t.skills.noSkillsMatch}
                  </p>
                ) : (
                  <div className="grid gap-1">
                    {searchMatchedSkills.map((skill) => (
                      <SkillRow
                        key={skill.name}
                        skill={skill}
                        toggling={togglingSkills.has(skill.name)}
                        onToggle={() => handleToggleSkill(skill)}
                        noDescriptionLabel={t.skills.noDescription}
                        locale={locale}
                      />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ) : view === "skills" ? (
            /* Skills list */
            <Card>
              <CardHeader className="py-3 px-4">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Package className="h-4 w-4" />
                    {activeCategory
                      ? prettyCategory(
                          activeCategory === "__none__" ? null : activeCategory,
                          t.common.general,
                        )
                      : t.skills.all}
                  </CardTitle>
                  <Badge tone="secondary" className="text-[10px]">
                    {t.skills.skillCount
                      .replace("{count}", String(activeSkills.length))
                      .replace("{s}", activeSkills.length !== 1 ? "s" : "")}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="px-4 pb-4">
                {activeSkills.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-8">
                    {skills.length === 0
                      ? t.skills.noSkills
                      : t.skills.noSkillsMatch}
                  </p>
                ) : (
                  <div className="grid gap-1">
                    {activeSkills.map((skill) => (
                      <SkillRow
                        key={skill.name}
                        skill={skill}
                        toggling={togglingSkills.has(skill.name)}
                        onToggle={() => handleToggleSkill(skill)}
                        noDescriptionLabel={t.skills.noDescription}
                        locale={locale}
                      />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            /* Toolsets grid */
            <>
              {filteredToolsets.length === 0 ? (
                <Card>
                  <CardContent className="py-8 text-center text-sm text-muted-foreground">
                    {t.skills.noToolsetsMatch}
                  </CardContent>
                </Card>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {filteredToolsets.map((ts) => {
                    const TsIcon = toolsetIcon(ts.name);
                    const labelText =
                      ts.label.replace(/^[\p{Emoji}\s]+/u, "").trim() ||
                      ts.name;

                    return (
                      <Card key={ts.name} className="relative">
                        <CardContent className="py-4">
                          <div className="flex items-start gap-3">
                            <TsIcon className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="font-medium text-sm">
                                  {labelText}
                                </span>
                                <Badge
                                  tone={ts.enabled ? "success" : "outline"}
                                  className="text-[10px]"
                                >
                                  {ts.enabled
                                    ? t.common.active
                                    : t.common.inactive}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground mb-2">
                                {ts.description}
                              </p>
                              {ts.enabled && !ts.configured && (
                                <p className="text-[10px] text-amber-300/80 mb-2">
                                  {t.skills.setupNeeded}
                                </p>
                              )}
                              {ts.tools.length > 0 && (
                                <div className="flex flex-wrap gap-1">
                                  {ts.tools.map((tool) => (
                                    <Badge
                                      key={tool}
                                      tone="secondary"
                                      className="text-[10px] font-mono"
                                    >
                                      {tool}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                              {ts.tools.length === 0 && (
                                <span className="text-[10px] text-muted-foreground/60">
                                  {ts.enabled
                                    ? t.skills.toolsetLabel.replace(
                                        "{name}",
                                        ts.name,
                                      )
                                    : t.skills.disabledForCli}
                                </span>
                              )}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>
      <PluginSlot name="skills:bottom" />
    </div>
  );
}

function SkillRow({
  skill,
  toggling,
  onToggle,
  noDescriptionLabel,
  locale,
}: SkillRowProps) {
  return (
    <div className="group flex items-start gap-3 px-3 py-2.5 transition-colors hover:bg-muted/40">
      <div className="pt-0.5 shrink-0">
        <Switch
          checked={skill.enabled}
          onCheckedChange={onToggle}
          disabled={toggling}
        />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span
            className={`font-mono-ui text-sm ${
              skill.enabled ? "text-foreground" : "text-muted-foreground"
            }`}
          >
            {skill.name}
          </span>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
          {skillDescription(skill, locale) || noDescriptionLabel}
        </p>
      </div>
    </div>
  );
}

function PanelItem({ active, icon: Icon, label, onClick }: PanelItemProps) {
  return (
    <ListItem
      active={active}
      onClick={onClick}
      className={cn(
        "rounded-sm whitespace-nowrap px-2.5 py-1.5",
        "font-mondwest text-[0.7rem] tracking-[0.08em] uppercase",
        active && "bg-foreground/90 text-background hover:text-background",
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="flex-1 truncate">{label}</span>
    </ListItem>
  );
}

interface PanelItemProps {
  active: boolean;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onClick: () => void;
}

interface SkillRowProps {
  noDescriptionLabel: string;
  locale: string;
  onToggle: () => void;
  skill: SkillInfo;
  toggling: boolean;
}
