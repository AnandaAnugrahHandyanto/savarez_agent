---
sidebar_position: 2
title: "スキルシステム"
description: "オンデマンドの知識ドキュメント — 漸進的開示、エージェント管理スキル、そしてSkills Hub"
---

# スキルシステム

スキルは、エージェントが必要なときに読み込めるオンデマンドの知識ドキュメントです。トークン使用量を最小限に抑えるために**漸進的開示（progressive disclosure）**のパターンに従っており、[agentskills.io](https://agentskills.io/specification)のオープン標準と互換性があります。

すべてのスキルは**`~/.hermes/skills/`**に格納されます。これがプライマリディレクトリであり信頼できる情報源（source of truth）です。新規インストール時には、バンドルされたスキルがリポジトリからコピーされます。Hubからインストールしたスキルやエージェントが作成したスキルもここに置かれます。エージェントは任意のスキルを変更または削除できます。

また、Hermesに**外部スキルディレクトリ**を指定することもできます。これはローカルディレクトリと並んでスキャンされる追加のフォルダです。後述の[外部スキルディレクトリ](#external-skill-directories)を参照してください。

あわせて参照:

- [バンドルスキルカタログ](/docs/reference/skills-catalog)
- [公式オプションスキルカタログ](/docs/reference/optional-skills-catalog)

## スキルの使い方

インストールされたすべてのスキルは、自動的にスラッシュコマンドとして利用できます:

```bash
# CLIまたは任意のメッセージングプラットフォームで:
/gif-search funny cats
/axolotl help me fine-tune Llama 3 on my dataset
/github-pr-workflow create a PR for the auth refactor
/plan design a rollout for migrating our auth provider

# スキル名だけを指定すると、スキルが読み込まれ、エージェントが何が必要かを尋ねます:
/excalidraw
```

バンドルされた`plan`スキルはよい例です。`/plan [request]`を実行するとスキルの指示が読み込まれ、Hermesに対して必要に応じてコンテキストを確認すること、タスクを実行する代わりにmarkdownの実装計画を書くこと、そしてその結果をアクティブなワークスペース／バックエンドの作業ディレクトリを基準とした`.hermes/plans/`配下に保存することを指示します。

自然な会話を通じてスキルとやり取りすることもできます:

```bash
hermes chat --toolsets skills -q "What skills do you have?"
hermes chat --toolsets skills -q "Show me the axolotl skill"
```

## 漸進的開示（Progressive Disclosure）

スキルはトークン効率のよい読み込みパターンを使用します:

```
Level 0: skills_list()           → [{name, description, category}, ...]   (~3k tokens)
Level 1: skill_view(name)        → Full content + metadata       (varies)
Level 2: skill_view(name, path)  → Specific reference file       (varies)
```

エージェントは、実際に必要になったときにのみスキルの全コンテンツを読み込みます。

## SKILL.mdのフォーマット

```markdown
---
name: my-skill
description: Brief description of what this skill does
version: 1.0.0
platforms: [macos, linux]     # 任意 — 特定のOSプラットフォームに制限する
metadata:
  hermes:
    tags: [python, automation]
    category: devops
    fallback_for_toolsets: [web]    # 任意 — 条件付き有効化（後述）
    requires_toolsets: [terminal]   # 任意 — 条件付き有効化（後述）
    config:                          # 任意 — config.yamlの設定
      - key: my.setting
        description: "What this controls"
        default: "value"
        prompt: "Prompt for setup"
---

# Skill Title

## When to Use
Trigger conditions for this skill.

## Procedure
1. Step one
2. Step two

## Pitfalls
- Known failure modes and fixes

## Verification
How to confirm it worked.
```

### プラットフォーム固有のスキル

スキルは`platforms`フィールドを使って、特定のオペレーティングシステムに自身を制限できます:

| 値 | 一致するもの |
|-------|---------|
| `macos` | macOS（Darwin） |
| `linux` | Linux |
| `windows` | Windows |

```yaml
platforms: [macos]            # macOSのみ（例: iMessage、Appleリマインダー、FindMy）
platforms: [macos, linux]     # macOSとLinux
```

設定されている場合、そのスキルは互換性のないプラットフォームでは、システムプロンプト、`skills_list()`、スラッシュコマンドから自動的に非表示になります。省略された場合、スキルはすべてのプラットフォームで読み込まれます。

### 条件付き有効化（フォールバックスキル）

スキルは、現在のセッションで利用可能なツールに基づいて、自身を自動的に表示または非表示にできます。これは**フォールバックスキル**に最も役立ちます。フォールバックスキルとは、プレミアムツールが利用できないときにのみ表示されるべき、無料またはローカルの代替手段です。

```yaml
metadata:
  hermes:
    fallback_for_toolsets: [web]      # これらのツールセットが利用不可のときのみ表示
    requires_toolsets: [terminal]     # これらのツールセットが利用可能のときのみ表示
    fallback_for_tools: [web_search]  # これらの個別ツールが利用不可のときのみ表示
    requires_tools: [terminal]        # これらの個別ツールが利用可能のときのみ表示
```

| フィールド | 動作 |
|-------|----------|
| `fallback_for_toolsets` | 列挙されたツールセットが利用可能なときにスキルは**非表示**になります。利用できないときに表示されます。 |
| `fallback_for_tools` | 同様ですが、ツールセットではなく個別のツールをチェックします。 |
| `requires_toolsets` | 列挙されたツールセットが利用不可のときにスキルは**非表示**になります。利用可能なときに表示されます。 |
| `requires_tools` | 同様ですが、個別のツールをチェックします。 |

**例:** 組み込みの`duckduckgo-search`スキルは`fallback_for_toolsets: [web]`を使用します。`FIRECRAWL_API_KEY`を設定している場合、webツールセットが利用可能となり、エージェントは`web_search`を使うため、DuckDuckGoスキルは非表示のままになります。APIキーがない場合、webツールセットは利用できないため、DuckDuckGoスキルが自動的にフォールバックとして表示されます。

条件付きフィールドを持たないスキルは、これまでとまったく同じように動作します。常に表示されます。

## 読み込み時の安全なセットアップ

スキルは、ディスカバリーから消えることなく、必要な環境変数を宣言できます:

```yaml
required_environment_variables:
  - name: TENOR_API_KEY
    prompt: Tenor API key
    help: Get a key from https://developers.google.com/tenor
    required_for: full functionality
```

値が欠けている場合、Hermesは、スキルがローカルのCLIで実際に読み込まれたときにのみ、安全にその値を尋ねます。セットアップをスキップしてそのままスキルを使い続けることもできます。メッセージングのインターフェースでは、チャット内でシークレットを尋ねることは決してありません。代わりに、ローカルで`hermes setup`または`~/.hermes/.env`を使うよう案内されます。

一度設定されると、宣言された環境変数は`execute_code`および`terminal`のサンドボックスへ**自動的に引き渡されます**。スキルのスクリプトは`$TENOR_API_KEY`を直接使用できます。スキル以外の環境変数については、`terminal.env_passthrough`設定オプションを使用してください。詳細は[環境変数のパススルー](/docs/user-guide/security#environment-variable-passthrough)を参照してください。

### スキルの設定項目

スキルは、`config.yaml`に保存される、シークレットではない設定項目（パスや好み）を宣言することもできます:

```yaml
metadata:
  hermes:
    config:
      - key: myplugin.path
        description: Path to the plugin data directory
        default: "~/myplugin-data"
        prompt: Plugin data directory path
```

設定はconfig.yamlの`skills.config`配下に保存されます。`hermes config migrate`は未設定の項目について入力を促し、`hermes config show`はそれらを表示します。スキルが読み込まれると、解決された設定値がコンテキストに注入されるため、エージェントは設定済みの値を自動的に把握します。

詳細は[スキル設定](/docs/user-guide/configuration#skill-settings)および[スキルの作成 — 設定項目](/docs/developer-guide/creating-skills#config-settings-configyaml)を参照してください。

## スキルディレクトリの構造

```text
~/.hermes/skills/                  # 唯一の信頼できる情報源
├── mlops/                         # カテゴリディレクトリ
│   ├── axolotl/
│   │   ├── SKILL.md               # メインの指示（必須）
│   │   ├── references/            # 追加のドキュメント
│   │   ├── templates/             # 出力フォーマット
│   │   ├── scripts/               # スキルから呼び出せるヘルパースクリプト
│   │   └── assets/                # 補助ファイル
│   └── vllm/
│       └── SKILL.md
├── devops/
│   └── deploy-k8s/                # エージェントが作成したスキル
│       ├── SKILL.md
│       └── references/
├── .hub/                          # Skills Hubの状態
│   ├── lock.json
│   ├── quarantine/
│   └── audit.log
└── .bundled_manifest              # シードされたバンドルスキルを追跡
```

## 外部スキルディレクトリ

Hermesの外部でスキルを管理している場合 — たとえば、複数のAIツールで利用する共有の`~/.agents/skills/`ディレクトリなど — それらのディレクトリもスキャンするようHermesに指示できます。

`~/.hermes/config.yaml`の`skills`セクションに`external_dirs`を追加します:

```yaml
skills:
  external_dirs:
    - ~/.agents/skills
    - /home/shared/team-skills
    - ${SKILLS_REPO}/skills
```

パスは`~`の展開と`${VAR}`環境変数の置換をサポートします。

### 動作の仕組み

- **読み取り専用**: 外部ディレクトリはスキルのディスカバリーのためにのみスキャンされます。エージェントがスキルを作成または編集するとき、常に`~/.hermes/skills/`へ書き込みます。
- **ローカルの優先**: 同じスキル名がローカルディレクトリと外部ディレクトリの両方に存在する場合、ローカル版が優先されます。
- **完全な統合**: 外部スキルは、システムプロンプトのインデックス、`skills_list`、`skill_view`、そして`/skill-name`スラッシュコマンドに表示されます。ローカルスキルとまったく変わりません。
- **存在しないパスは静かにスキップされる**: 設定されたディレクトリが存在しない場合、Hermesはエラーを出さずにそれを無視します。すべてのマシンに存在するとは限らないオプションの共有ディレクトリに便利です。

### 例

```text
~/.hermes/skills/               # ローカル（プライマリ、読み書き可能）
├── devops/deploy-k8s/
│   └── SKILL.md
└── mlops/axolotl/
    └── SKILL.md

~/.agents/skills/               # 外部（読み取り専用、共有）
├── my-custom-workflow/
│   └── SKILL.md
└── team-conventions/
    └── SKILL.md
```

4つのスキルすべてがスキルインデックスに表示されます。`my-custom-workflow`という名前の新しいスキルをローカルに作成すると、外部版を上書き（シャドウ）します。

## エージェント管理スキル（skill_manageツール）

エージェントは`skill_manage`ツールを介して、自身のスキルを作成、更新、削除できます。これはエージェントの**手続き的記憶**です。エージェントが自明でないワークフローを把握したとき、その方法を将来の再利用のためにスキルとして保存します。

### エージェントがスキルを作成するとき

- 複雑なタスク（5回以上のツール呼び出し）を正常に完了したあと
- エラーや行き詰まりに遭遇し、うまくいく経路を見つけたとき
- ユーザーがそのアプローチを修正したとき
- 自明でないワークフローを発見したとき

### アクション

| アクション | 用途 | 主なパラメータ |
|--------|---------|------------|
| `create` | ゼロから新しいスキルを作成 | `name`、`content`（SKILL.md全体）、任意の`category` |
| `patch` | 対象を絞った修正（推奨） | `name`、`old_string`、`new_string` |
| `edit` | 大きな構造の書き換え | `name`、`content`（SKILL.md全体の置換） |
| `delete` | スキルを完全に削除 | `name` |
| `write_file` | サポートファイルの追加／更新 | `name`、`file_path`、`file_content` |
| `remove_file` | サポートファイルの削除 | `name`、`file_path` |

:::tip
更新には`patch`アクションが推奨されます。変更されたテキストのみがツール呼び出しに現れるため、`edit`よりもトークン効率がよいです。
:::

## Skills Hub

オンラインのレジストリ、`skills.sh`、直接のwell-knownスキルエンドポイント、そして公式オプションスキルから、スキルを閲覧、検索、インストール、管理します。

### よく使うコマンド

```bash
hermes skills browse                              # すべてのHubスキルを閲覧（公式が先）
hermes skills browse --source official            # 公式オプションスキルのみを閲覧
hermes skills search kubernetes                   # すべてのソースを検索
hermes skills search react --source skills-sh     # skills.shディレクトリを検索
hermes skills search https://mintlify.com/docs --source well-known
hermes skills inspect openai/skills/k8s           # インストール前にプレビュー
hermes skills install openai/skills/k8s           # セキュリティスキャン付きでインストール
hermes skills install official/security/1password
hermes skills install skills-sh/vercel-labs/json-render/json-render-react --force
hermes skills install well-known:https://mintlify.com/docs/.well-known/skills/mintlify
hermes skills install https://sharethis.chat/SKILL.md              # 直接URL（単一ファイルのSKILL.md）
hermes skills install https://example.com/SKILL.md --name my-skill # frontmatterに名前がない場合に名前を上書き
hermes skills list --source hub                   # Hubからインストールしたスキルを一覧表示
hermes skills check                               # インストール済みHubスキルの上流更新を確認
hermes skills update                              # 必要に応じて上流の変更を反映してHubスキルを再インストール
hermes skills audit                               # すべてのHubスキルをセキュリティ再スキャン
hermes skills uninstall k8s                       # Hubスキルを削除
hermes skills reset google-workspace              # バンドルスキルを「user-modified」状態から解除（後述）
hermes skills reset google-workspace --restore    # ローカルの編集を削除してバンドル版も復元
hermes skills publish skills/my-skill --to github --repo owner/repo
hermes skills snapshot export setup.json          # スキル設定をエクスポート
hermes skills tap add myorg/skills-repo           # カスタムGitHubソースを追加
```

### サポートされるHubソース

| ソース | 例 | 備考 |
|--------|---------|-------|
| `official` | `official/security/1password` | Hermesに同梱されるオプションスキル。 |
| `skills-sh` | `skills-sh/vercel-labs/agent-skills/vercel-react-best-practices` | `hermes skills search <query> --source skills-sh`で検索可能。skills.shのslugがリポジトリのフォルダと異なる場合、Hermesはエイリアス形式のスキルを解決します。 |
| `well-known` | `well-known:https://mintlify.com/docs/.well-known/skills/mintlify` | ウェブサイト上の`/.well-known/skills/index.json`から直接提供されるスキル。サイトまたはドキュメントのURLを使って検索します。 |
| `url` | `https://sharethis.chat/SKILL.md` | 単一ファイルの`SKILL.md`への直接HTTP(S) URL。名前の解決順: frontmatter → URL slug → 対話的プロンプト → `--name`フラグ。 |
| `github` | `openai/skills/k8s` | GitHubのリポジトリ／パスからの直接インストールおよびカスタムタップ。 |
| `clawhub`、`lobehub`、`claude-marketplace` | ソース固有の識別子 | コミュニティまたはマーケットプレイスの統合。 |

### 統合されたHubとレジストリ

Hermesは現在、以下のスキルエコシステムとディスカバリーソースと統合しています:

#### 1. 公式オプションスキル（`official`）

これらはHermesリポジトリ自体で管理され、組み込みの信頼レベルでインストールされます。

- カタログ: [公式オプションスキルカタログ](../../reference/optional-skills-catalog)
- リポジトリ内のソース: `optional-skills/`
- 例:

```bash
hermes skills browse --source official
hermes skills install official/security/1password
```

#### 2. skills.sh（`skills-sh`）

これはVercelの公開スキルディレクトリです。Hermesはこれを直接検索し、スキルの詳細ページを確認し、エイリアス形式のslugを解決し、基盤となるソースリポジトリからインストールできます。

- ディレクトリ: [skills.sh](https://skills.sh/)
- CLI／ツールのリポジトリ: [vercel-labs/skills](https://github.com/vercel-labs/skills)
- Vercel公式スキルリポジトリ: [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills)
- 例:

```bash
hermes skills search react --source skills-sh
hermes skills inspect skills-sh/vercel-labs/json-render/json-render-react
hermes skills install skills-sh/vercel-labs/json-render/json-render-react --force
```

#### 3. well-knownスキルエンドポイント（`well-known`）

これは、`/.well-known/skills/index.json`を公開しているサイトからのURLベースのディスカバリーです。単一の集中型Hubではなく、ウェブのディスカバリー規約です。

- ライブエンドポイントの例: [Mintlifyドキュメントのスキルインデックス](https://mintlify.com/docs/.well-known/skills/index.json)
- 参照用のサーバー実装: [vercel-labs/skills-handler](https://github.com/vercel-labs/skills-handler)
- 例:

```bash
hermes skills search https://mintlify.com/docs --source well-known
hermes skills inspect well-known:https://mintlify.com/docs/.well-known/skills/mintlify
hermes skills install well-known:https://mintlify.com/docs/.well-known/skills/mintlify
```

#### 4. 直接GitHubスキル（`github`）

Hermesは、GitHubリポジトリおよびGitHubベースのタップから直接インストールできます。リポジトリ／パスをすでに把握している場合や、独自のカスタムソースリポジトリを追加したい場合に便利です。

デフォルトのタップ（セットアップなしで閲覧可能）:
- [openai/skills](https://github.com/openai/skills)
- [anthropics/skills](https://github.com/anthropics/skills)
- [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills)
- [garrytan/gstack](https://github.com/garrytan/gstack)

- 例:

```bash
hermes skills install openai/skills/k8s
hermes skills tap add myorg/skills-repo
```

#### 5. ClawHub（`clawhub`）

コミュニティソースとして統合された、サードパーティのスキルマーケットプレイスです。

- サイト: [clawhub.ai](https://clawhub.ai/)
- Hermesのソースid: `clawhub`

#### 6. Claudeマーケットプレイス形式のリポジトリ（`claude-marketplace`）

Hermesは、Claude互換のプラグイン／マーケットプレイスマニフェストを公開するマーケットプレイスリポジトリをサポートします。

既知の統合済みソースには次のものが含まれます:
- [anthropics/skills](https://github.com/anthropics/skills)
- [aiskillstore/marketplace](https://github.com/aiskillstore/marketplace)

Hermesのソースid: `claude-marketplace`

#### 7. LobeHub（`lobehub`）

Hermesは、LobeHubの公開カタログにあるエージェントエントリを検索し、インストール可能なHermesスキルへ変換できます。

- サイト: [LobeHub](https://lobehub.com/)
- 公開エージェントインデックス: [chat-agents.lobehub.com](https://chat-agents.lobehub.com/)
- バックエンドのリポジトリ: [lobehub/lobe-chat-agents](https://github.com/lobehub/lobe-chat-agents)
- Hermesのソースid: `lobehub`

#### 8. 直接URL（`url`）

任意のHTTP(S) URLから単一ファイルの`SKILL.md`を直接インストールします。作者が自身のサイトでスキルをホストしている場合（Hubのリストがなく、入力すべきGitHubのパスもない場合）に便利です。HermesはURLを取得し、YAML frontmatterを解析し、セキュリティスキャンを行ってインストールします。

- Hermesのソースid: `url`
- 識別子: URL自体（プレフィックスは不要）
- スコープ: **単一ファイルの`SKILL.md`**のみ。`references/`や`scripts/`を持つ複数ファイルのスキルにはマニフェストが必要で、上記の他のソースのいずれかを介して公開する必要があります。

```bash
hermes skills install https://sharethis.chat/SKILL.md
hermes skills install https://example.com/my-skill/SKILL.md --category productivity
```

名前の解決は次の順序で行われます:
1. SKILL.mdのYAML frontmatterの`name:`フィールド（推奨 — 適切に整形されたスキルはすべてこれを持っています）。
2. URLパスの親ディレクトリ名（例: `.../my-skill/SKILL.md` → `my-skill`、または`.../my-skill.md` → `my-skill`）。有効な識別子（`^[a-z][a-z0-9_-]*$`）である場合。
3. TTYを持つターミナル上での対話的プロンプト。
4. 非対話的なインターフェース（TUI内の`/skills install`スラッシュコマンド、ゲートウェイプラットフォーム、スクリプト）では、`--name`での上書きを示す明確なエラー。

```bash
# frontmatterに名前がなく、URLのslugも役に立たない場合 — 名前を指定する:
hermes skills install https://example.com/SKILL.md --name sharethis-chat

# または、チャットセッション内で:
/skills install https://example.com/SKILL.md --name sharethis-chat
```

信頼レベルは常に`community`です。他のあらゆるソースと同じセキュリティスキャンが実行されます。URLはインストール識別子として保存されるため、リフレッシュしたいときに`hermes skills update`が自動的に同じURLから再取得します。

### セキュリティスキャンと`--force`

Hubからインストールされたすべてのスキルは、データの持ち出し、プロンプトインジェクション、破壊的なコマンド、サプライチェーンのシグナル、その他の脅威をチェックする**セキュリティスキャナー**を通過します。

`hermes skills inspect ...`は、利用可能な場合に上流のメタデータも表示するようになりました:
- リポジトリのURL
- skills.shの詳細ページURL
- インストールコマンド
- 週間インストール数
- 上流のセキュリティ監査ステータス
- well-knownのインデックス／エンドポイントURL

サードパーティのスキルをレビュー済みで、危険ではないポリシーブロックを上書きしたい場合は`--force`を使用します:

```bash
hermes skills install skills-sh/anthropics/skills/pdf --force
```

重要な動作:
- `--force`は、caution／warn形式の検出結果に対するポリシーブロックを上書きできます。
- `--force`は`dangerous`というスキャン判定を上書き**しません**。
- 公式オプションスキル（`official/...`）は組み込みの信頼として扱われ、サードパーティの警告パネルを表示しません。

### 信頼レベル

| レベル | ソース | ポリシー |
|-------|--------|--------|
| `builtin` | Hermesに同梱 | 常に信頼される |
| `official` | リポジトリ内の`optional-skills/` | 組み込みの信頼、サードパーティ警告なし |
| `trusted` | `openai/skills`や`anthropics/skills`などの信頼されたレジストリ／リポジトリ | コミュニティソースよりも寛容なポリシー |
| `community` | それ以外すべて（`skills.sh`、well-knownエンドポイント、カスタムGitHubリポジトリ、ほとんどのマーケットプレイス） | 危険でない検出結果は`--force`で上書き可能。`dangerous`判定はブロックされたまま |

### 更新のライフサイクル

Hubは、インストール済みスキルの上流のコピーを再チェックできるだけの来歴情報（provenance）を追跡するようになりました:

```bash
hermes skills check          # どのインストール済みHubスキルが上流で変更されたかを報告
hermes skills update         # 更新が利用可能なスキルのみを再インストール
hermes skills update react   # 特定のインストール済みHubスキル1つを更新
```

これは、保存されたソース識別子と現在の上流バンドルのコンテンツハッシュを使って、差分（ドリフト）を検出します。

:::tip GitHubのレート制限
Skills Hubの操作はGitHub APIを使用しており、認証されていないユーザーには毎時60リクエストのレート制限があります。インストールや検索の際にレート制限エラーが表示される場合は、`.env`ファイルに`GITHUB_TOKEN`を設定して、制限を毎時5,000リクエストに引き上げてください。これが発生したとき、エラーメッセージには実行可能なヒントが含まれます。
:::

### カスタムスキルタップの公開

キュレーションしたスキルのセットを共有したい場合 — チーム、組織、あるいは公開向けに — それらを**タップ**として公開できます。タップとは、他のHermesユーザーが`hermes skills tap add <owner/repo>`で追加するGitHubリポジトリです。サーバーも、レジストリへのサインアップも、リリースパイプラインも不要です。`SKILL.md`ファイルのディレクトリがあるだけです。

#### リポジトリのレイアウト

タップは、次のようにレイアウトされた任意のGitHubリポジトリ（公開または非公開 — 非公開には`GITHUB_TOKEN`が必要）です:

```
owner/repo
├── skills/                       # デフォルトのパス。タップごとに設定可能
│   ├── my-workflow/
│   │   ├── SKILL.md              # 必須
│   │   ├── references/           # 任意のサポートファイル
│   │   ├── templates/
│   │   └── scripts/
│   ├── another-skill/
│   │   └── SKILL.md
│   └── third-skill/
│       └── SKILL.md
└── README.md                     # 任意だが役立つ
```

ルール:
- 各スキルは、タップのルートパス（デフォルトは`skills/`）配下の独自のディレクトリに置かれます。
- ディレクトリ名がスキルのインストールslugになります。
- 各スキルディレクトリには、標準の[SKILL.md frontmatter](#skillmd-format)（`name`、`description`、加えて任意の`metadata.hermes.tags`、`version`、`author`、`platforms`、`metadata.hermes.config`）を含む`SKILL.md`が必要です。
- `references/`、`templates/`、`scripts/`、`assets/`などのサブディレクトリは、インストール時に`SKILL.md`とともにダウンロードされます。
- ディレクトリ名が`.`または`_`で始まるスキルは無視されます。

Hermesは、タップパスのすべてのサブディレクトリを列挙し、それぞれに`SKILL.md`があるかを調べることで、スキルを検出します。

#### 最小限のタップの例

```
my-org/hermes-skills
└── skills/
    └── deploy-runbook/
        └── SKILL.md
```

`skills/deploy-runbook/SKILL.md`:

```markdown
---
name: deploy-runbook
description: Our deployment runbook — services, rollback, Slack channels
version: 1.0.0
author: My Org Platform Team
metadata:
  hermes:
    tags: [deployment, runbook, internal]
---

# Deploy Runbook

Step 1: ...
```

それをGitHubにプッシュすると、どのHermesユーザーも購読してインストールできます:

```bash
hermes skills tap add my-org/hermes-skills
hermes skills search deploy
hermes skills install my-org/hermes-skills/deploy-runbook
```

#### デフォルト以外のパス

スキルが`skills/`配下にない場合（既存のプロジェクトに`skills/`サブツリーを追加するときによくあります）、`~/.hermes/.hub/taps.json`のタップエントリを編集します:

```json
{
  "taps": [
    {"repo": "my-org/platform-docs", "path": "internal/skills/"}
  ]
}
```

`hermes skills tap add` CLIは、新しいタップのデフォルトを`path: "skills/"`に設定します。別のパスが必要な場合は、ファイルを直接編集してください。`hermes skills tap list`は、タップごとの有効なパスを表示します。

#### 個別のスキルを直接インストールする（タップを追加せずに）

ユーザーは、リポジトリ全体をタップとして追加せずに、任意の公開GitHubリポジトリから単一のスキルをインストールすることもできます:

```bash
hermes skills install owner/repo/skills/my-workflow
```

ユーザーにレジストリ全体への購読を求めることなく、1つのスキルを共有したい場合に便利です。

#### タップの信頼レベル

新しいタップにはデフォルトで`community`の信頼が割り当てられます。それらからインストールされたスキルは標準のセキュリティスキャンを通過し、初回インストール時にサードパーティの警告パネルを表示します。組織や広く信頼されたソースがより高い信頼を得るべき場合は、そのリポジトリを`tools/skills_hub.py`の`TRUSTED_REPOS`に追加します（Hermesコアへのプルリクエストが必要です）。

#### タップの管理

```bash
hermes skills tap list                                # 設定されたすべてのタップを表示
hermes skills tap add myorg/skills-repo               # 追加（デフォルトパス: skills/）
hermes skills tap remove myorg/skills-repo            # 削除
```

実行中のセッション内で:

```
/skills tap list
/skills tap add myorg/skills-repo
/skills tap remove myorg/skills-repo
```

タップは`~/.hermes/.hub/taps.json`に保存されます（必要に応じて作成されます）。

## バンドルスキルの更新（`hermes skills reset`）

Hermesは、リポジトリ内の`skills/`に一連のバンドルスキルを同梱しています。インストール時、および`hermes update`のたびに、同期パスがそれらを`~/.hermes/skills/`へコピーし、各スキル名を同期時のコンテンツハッシュ（**オリジンハッシュ**）にマッピングするマニフェストを`~/.hermes/skills/.bundled_manifest`に記録します。

各同期時に、Hermesはローカルのコピーのハッシュを再計算し、それをオリジンハッシュと比較します:

- **変更なし** → 上流の変更を安全に取り込めるため、新しいバンドル版をコピーし、新しいオリジンハッシュを記録します。
- **変更あり** → **user-modified**として扱われ、以後ずっとスキップされるため、あなたの編集が上書きされることはありません。

この保護はよくできていますが、1つだけ鋭いエッジ（落とし穴）があります。バンドルスキルを編集し、あとでその変更を破棄して`~/.hermes/hermes-agent/skills/`からコピー＆ペーストするだけでバンドル版に戻したい場合、マニフェストには最後に成功した同期が実行された時点の*古い*オリジンハッシュがまだ保持されています。新たにコピー＆ペーストした内容（現在のバンドルハッシュ）はその古いオリジンハッシュと一致しないため、同期はそれをuser-modifiedとしてフラグし続けます。

`hermes skills reset`はその脱出口です:

```bash
# 安全: このスキルのマニフェストエントリをクリアします。現在のコピーは保持され、
# 次回の同期がそれを基準に再ベースライン化するため、以後の更新は通常どおり機能します。
hermes skills reset google-workspace

# 完全な復元: ローカルのコピーも削除し、現在のバンドル版を再コピーします。
# 手つかずの上流スキルに戻したいときに使用します。
hermes skills reset google-workspace --restore

# 非対話的（例: スクリプトやTUIモード内）— --restoreの確認をスキップします。
hermes skills reset google-workspace --restore --yes
```

同じコマンドは、チャット内でもスラッシュコマンドとして機能します:

```text
/skills reset google-workspace
/skills reset google-workspace --restore
```

:::note プロファイル
各プロファイルは、それぞれの`HERMES_HOME`配下に独自の`.bundled_manifest`を持つため、`hermes -p coder skills reset <name>`はそのプロファイルにのみ影響します。
:::

### スラッシュコマンド（チャット内）

同じすべてのコマンドが`/skills`で機能します:

```text
/skills browse
/skills search react --source skills-sh
/skills search https://mintlify.com/docs --source well-known
/skills inspect skills-sh/vercel-labs/json-render/json-render-react
/skills install openai/skills/skill-creator --force
/skills check
/skills update
/skills reset google-workspace
/skills list
```

公式オプションスキルは、引き続き`official/security/1password`や`official/migration/openclaw-migration`のような識別子を使用します。
