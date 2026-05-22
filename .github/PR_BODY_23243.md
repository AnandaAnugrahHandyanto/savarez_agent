## What does this PR do?

Adds a **full i18n infrastructure** to the Hermes TUI and Web Dashboard, with a complete **Chinese (zh) translation**.

Core design goals:
- **Dig the well, don't pour water** — 16-language framework is ready. Any translator can add a language by creating one file and filling in translations. No architecture code to touch.
- **Clean module boundaries** — Pure functions (`translate()`) and React hooks (`useI18n()`) are strictly separated. Slash commands and non-React modules can use translations without pulling in React.
- **Type-safe** — `TranslationKey` is inferred from the EN catalog. TypeScript enforces that every language pack covers every key at compile time.
- **Zero impact on English users** — When `locale !== 'zh'`, all paths return the original English text with identical behavior.

## Related Issue

Fixes #23224

## Type of Change

- [x] ✨ New feature (non-breaking change that adds functionality)

## Changes Made

### TUI i18n framework (`ui-tui/src/i18n/`) — 18 new files

| File | Role |
|------|------|
| `types.ts` | 16-language `Locale`, `LangPack` interface, `GlossaryTerm` type-level terminology registry |
| `en.ts` | Full EN language pack (~442 keys), authoritative source of `TranslationKey` type |
| `zh.ts` | Full ZH language pack (~442 keys, 1:1 with EN) |
| `index.tsx` | Pure function layer (`translate`/`translateStatus`/`getToolVerb`/`getThinkingVerbs`) + React layer (`I18nProvider`/`useI18n`/`toolsetLabel`) + CATALOGS dictionary + fallback chain |
| 14 language shell files | `ja.ts`, `de.ts`, `es.ts`, `fr.ts`, `tr.ts`, `uk.ts`, `af.ts`, `ko.ts`, `it.ts`, `ga.ts`, `pt.ts`, `ru.ts`, `hu.ts`, `zh-hant.ts` — currently `export { en } from './en.js'` re-exports. Framework is wired; translators only need to edit their file and add it to CATALOGS |

**Fallback chain:**
```
getPack(locale) ?? en           ← missing language pack → English pack
pack[key] ?? en[key] ?? key     ← missing key → English value → raw key
```

**`TranslationKey` type inference:** derived from `en.ts` catalog — single authority. New language packs must cover all keys (TypeScript compile-time enforcement). Non-en/zh users see English automatically until translation is complete.

### Language wiring

| Layer | File | Change |
|-------|------|--------|
| Python config | `agent/i18n.py` | `get_language()`: `HERMES_LANGUAGE` > `display.language` > `en` |
| Python gateway | `tui_gateway/server.py` | `resolve_language()` resolves user language |
| Gateway startup | `tui_gateway/entry.py`, `ws.py` | `gateway.ready` payload carries `language` |
| TUI state | `uiStore.ts`, `interfaces.ts` | `UiState.locale`, default `'en'` |
| TUI entry | `ui-tui/src/app.tsx` | `<I18nProvider locale={locale}>` wraps the app |
| Event handler | `createGatewayEventHandler.ts` | `gateway.ready.language` → `patchUiState({ locale })` |
| Config sync | `useConfigSync.ts` | Updates locale on `display.language` change |
| Non-React modules | `domain/messages.ts`, slash commands, etc. | Pure function `translate(locale, key)` replaces hardcoded strings |

### TUI component i18n (~30 files)

Replaced ~70+ hardcoded English strings with i18n key calls, covering:
- Status bar verb rotation (FaceTicker thinking verbs — 15 en/zh aligned)
- Hotkey descriptions (`hotkeys.ts` — TranslationKey array, resolved in components)
- Input placeholders (`input.placeholder1–7` — locale-aware)
- Model picker (~25 keys: provider/model/key input/status)
- Confirm/approve/clarify dialogs
- SessionPanel welcome screen / Branding
- Slash command output (`/help`, `/status`, `/sessions`, `/details`, `/debug`, `/setup`)
- Toolset name mapping (`toolsetLabel()` — backend data → translation table)
- Error/warning/protocol noise system messages

### Dashboard Chinese (`web/src/`)

| File | Change |
|------|--------|
| `web/src/i18n/zh.ts` | Full Chinese translation |
| `web/src/i18n/schemaZh.ts` | Config page field label mapping (~180 keys, for AutoField) |
| `web/src/components/AutoField.tsx` | Uses `schemaZh` when `locale='zh'` |
| `web/src/i18n/types.ts` | Extended i18n sections for new keys |
| `web/src/App.tsx` | `Loading chat…` → `t.app.loadingChat` |
| Multiple components | modelPicker, OAuth, ThemeSwitcher — wired to existing keys |

### Plugin nav i18n

| File | Change |
|------|--------|
| `plugins/*/dashboard/manifest.json` | Added `labelKey`/`descriptionKey` to all 3 plugins |
| `web/src/plugins/types.ts` | Optional `labelKey`/`descriptionKey` on `PluginManifest` |
| `hermes_cli/web_server.py` | `_discover_dashboard_plugins()` forwards `labelKey` |
| `web/src/App.tsx` | `buildNavItems()` passes `labelKey` to `NavItem` |

## How to Test

### 1. Enable Chinese
```bash
hermes config set display.language zh
```

### 2. TUI verification
```bash
hermes --tui
```
Expected: status bar, `/help` output, hotkey hints, confirm dialog buttons, error messages, input placeholders — all in Chinese.

### 3. Verify English is untouched
```bash
hermes config set display.language en
hermes --tui
```
All display should be identical to pre-PR behavior.

### 4. Dashboard verification
1. Open `http://localhost:18923`
2. Switch to `CN 中文` via the language switcher (bottom-left)
3. Config page field labels → Chinese
4. Sidebar plugin names → Chinese (看板 / 成就 / 示例)
5. Switch back to EN → everything restores

### 5. Type check and build
```bash
cd ui-tui && npx tsc --noEmit && pnpm run build
cd web && pnpm run build
```

### 6. Verify extensibility (new language proof)
```bash
# 1. cp ui-tui/src/i18n/zh.ts ui-tui/src/i18n/ja.ts
# 2. edit translations in ja.ts
# 3. add import + one line to CATALOGS in index.tsx
# 4. pnpm build → passes
```

## Checklist

### Code
- [x] I've read the Contributing Guide
- [x] My commit messages follow Conventional Commits
- [x] I searched for existing PRs to make sure this isn't a duplicate
- [x] My PR contains **only** changes related to this feature
- [ ] I've run `pytest tests/ -q` and all tests pass *(CI will run full suite)*
- [ ] I've added tests for my changes *(i18n is display-layer; vitest suite covers key coverage + fallback)*
- [x] I've tested on my platform: **WSL2 (Ubuntu) + Windows 11**

### Documentation & Housekeeping
- [x] I've updated relevant documentation — or N/A
- [x] I've updated `cli-config.yaml.example` — or N/A *(`display.language` already exists)*
- [x] I've considered cross-platform impact — or N/A *(pure TS + Python)*
- [x] I've updated tool descriptions/schemas — or N/A

### Compatibility
- English users unaffected: all paths return original text when `locale !== 'zh'`
- No changes to non-i18n architecture: Python gateway adds one `language` field; TUI component changes are display-layer only
- Backward compatible: `display.language` defaults to `en`; users without config see no difference

### New language onboarding
1. `cp ui-tui/src/i18n/zh.ts ui-tui/src/i18n/ja.ts`
2. Edit translations
3. Add `ja` to the `CATALOGS` dictionary in `ui-tui/src/i18n/index.tsx`
4. `pnpm build`

TypeScript enforces full TranslationKey coverage automatically.

---

## 这个 PR 做了什么？

为 Hermes 的 **TUI（终端界面）和 Web Dashboard** 添加完整的多语言 i18n 基础设施，并完成**中文（zh）**翻译。

核心设计目标：
- **挖井，不是倒水** — 建好 16 语言框架，任何语言贡献者只需建文件 + 翻译内容，不用碰架构代码
- **模块边界干净** — 纯函数（`translate()`）和 React Hook（`useI18n()`）严格分层，slash 命令和非 React 模块也能用翻译
- **类型安全** — `TranslationKey` 从 EN 翻译包推断，TypeScript 编译器保证所有语言覆盖所有 key
- **不破坏英文用户** — `locale !== 'zh'` 时所有路径返回原文，行为完全不变

## 关联 Issue

Fixes #23224

## 变更类型

- [x] ✨ 新功能

## 具体变更

### TUI i18n 框架（`ui-tui/src/i18n/`）— 新增 18 文件

| 文件 | 职责 |
|------|------|
| `types.ts` | 16 语言 `Locale`、`LangPack` 接口、`GlossaryTerm` 类型级术语注册表 |
| `en.ts` | 完整 EN 语言包（~442 key），是 `TranslationKey` 的类型权威来源 |
| `zh.ts` | 完整 ZH 语言包（~442 key，与 EN 一一对应） |
| `index.tsx` | 纯函数层 + React 层 + CATALOGS 字典 + fallback 链 |
| 14 个语言壳文件 | `ja.ts`、`de.ts` 等 — 目前是 `export { en }` re-export，框架就绪，翻译者只需编辑对应文件并加入 CATALOGS |

**Fallback 链：**
```
getPack(locale) ?? en           ← 语言包缺失 → 英文包
pack[key] ?? en[key] ?? key     ← key 缺失 → 英文值 → 裸 key
```

**TranslationKey 类型推断：** 从 `en.ts` catalog 推断，唯一权威。新语言包必须覆盖所有 key（TS 编译时强制）。

### 语言接线

| 层 | 文件 | 改动 |
|----|------|------|
| Python 配置 | `agent/i18n.py` | `get_language()` |
| Python gateway | `tui_gateway/server.py` | `resolve_language()` |
| Gateway 启动 | `entry.py`、`ws.py` | `gateway.ready` 携带 `language` |
| TUI 状态 | `uiStore.ts`、`interfaces.ts` | `UiState.locale` |
| TUI 入口 | `app.tsx` | `<I18nProvider>` |
| 事件处理 | `createGatewayEventHandler.ts` | locale 同步 |
| 配置同步 | `useConfigSync.ts` | 语言变更时更新 |
| 非 React 模块 | slash 命令等 | `translate(locale, key)` 替代硬编码 |

### TUI 组件翻译（~30 文件）

将 ~70+ 处硬编码英文替换为 i18n key，覆盖状态栏动词、快捷键、占位符、模型选择器、确认对话框、欢迎界面、slash 命令输出、工具集名称映射、系统消息等。

### Dashboard 中文（`web/src/`）

- 完整中文翻译 + 配置页 schema 映射（`schemaZh.ts`，~180 key）
- AutoField 在中文本地化下使用 schemaZh
- 组件接线已有 key

### 插件导航翻译

- 三个插件 manifest 各加 `labelKey`
- Python 后端透传 `labelKey` → 前端 NavItem 消费

## 如何测试

1. `hermes config set display.language zh` → TUI 全中文化
2. 切回 `en` → 所有显示与修改前完全一致
3. Dashboard 左下角切 `CN 中文` → 配置页/侧边栏中文化
4. `pnpm build` 通过（ui-tui + web）
5. 加新语言：建文件 → 加 CATALOGS → build 通过

## Checklist

- [x] 已读 Contributing Guide
- [x] 不破坏英文用户、不侵入非 i18n 架构、向后兼容
- [x] 新语言加入路径清晰（建文件 → CATALOGS → build）
- [x] 测试平台：WSL2 (Ubuntu) + Windows 11
