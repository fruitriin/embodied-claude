# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Claude に身体（目・首・耳・声・脳）を与える MCP サーバー群。各サーバーは独立した Python パッケージとして構成される。

## 開発コマンド

すべてのサブプロジェクトで共通：

```bash
# 依存関係インストール（dev含む）
cd <project-dir>
uv sync --extra dev

# リント
uv run ruff check .

# テスト実行
uv run pytest -v

# 単一テスト実行
uv run pytest tests/test_memory.py -v
uv run pytest tests/test_memory.py::test_save_and_search -v

# サーバー起動
uv run <entry-point>
```

### エントリーポイント

| プロジェクト | コマンド | エントリーポイント |
|------------|---------|------------------|
| wifi-cam-mcp | `uv run wifi-cam-mcp` | `wifi_cam_mcp.server:main` |
| memory-mcp | `uv run memory-mcp` | `memory_mcp.server:main` |
| memory-mcp | `uv run memory-migrate` | `memory_mcp.migrate:main`（ChromaDB→PostgreSQL移行） |
| elevenlabs-t2s-mcp | `uv run elevenlabs-t2s` | `elevenlabs_t2s_mcp.server:main` |
| voicevox-mcp | `uv run voicevox-mcp` | `voicevox_mcp.server:main` |
| usb-webcam-mcp | `uv run usb-webcam-mcp` | `usb_webcam_mcp.server:main` |
| system-temperature-mcp | `uv run system-temperature-mcp` | `system_temperature_mcp.server:main` |
| installer | `uv run embodied-claude-installer` | `installer.main:main`（PyQt6 GUI） |

### コミット前チェック（必須）

変更した各サブプロジェクトで実行：

```bash
cd <project-dir>
uv run ruff check .    # lint エラーがないこと
uv run pytest -v       # テストが通ること
```

### Ruff 設定の違い

- **memory-mcp**: `line-length = 120`（server.py が複雑なため）
- **wifi-cam-mcp**: `line-length = 100`、server.py は E501 除外
- **voicevox-mcp**: `line-length = 100`、server.py は E501 除外
- **他プロジェクト**: 各 pyproject.toml を参照
- **共通**: `select = ["E", "F", "I", "N", "W"]`、`target-version = "py310"`

## アーキテクチャ

### MCP サーバー共通パターン

すべてのサーバーは `mcp.server.Server`（FastMCP ではない）を使用し、同じ構造に従う：

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server

class XxxMCPServer:
    def __init__(self):
        self._server = Server("server-name")
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        @self._server.list_tools()
        async def list_tools() -> list[Tool]: ...

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]: ...

    async def run(self) -> None:
        async with stdio_server() as (read, write):
            await self._server.run(read, write, ...)
```

例外: `usb-webcam-mcp` のみ関数ベース（クラスなし）。

### Config パターン

各サーバーの設定は `frozen dataclass` + `from_env()` で環境変数から生成：

```python
@dataclass(frozen=True)
class XxxConfig:
    @classmethod
    def from_env(cls) -> "XxxConfig":
        load_dotenv()
        return cls(field=os.getenv("ENV_VAR", "default"), ...)
```

### サブプロジェクト間の関係

```
Claude Code ──MCP stdio──▶ 各サーバー（独立プロセス）
                              │
                              ├── wifi-cam-mcp ──ONVIF──▶ Tapoカメラ
                              │                  ──RTSP──▶ ffmpeg（キャプチャ/録音）
                              │                  ──Whisper──▶ 音声認識
                              │
                              ├── memory-mcp ──────────▶ PostgreSQL（pgvector + pgroonga）
                              │                          SentenceTransformer（埋め込み）
                              │
                              ├── elevenlabs-t2s-mcp ──▶ ElevenLabs API
                              │                    ──▶ go2rtc（オーディオバックチャネル）
                              │
                              ├── voicevox-mcp ──────▶ VOICEVOX Engine（ローカルTTS）
                              │                  ──▶ go2rtc（オーディオバックチャネル）
                              │
                              ├── usb-webcam-mcp ──▶ OpenCV
                              └── system-temperature-mcp ──▶ OS sensors
```

### memory-mcp の内部構造

最も複雑なサブプロジェクト。Phase 1〜6 で段階的に構築された記憶システム：

- `postgres_store.py`: PostgreSQL コネクション管理（asyncpg）
- `schema.py`: DDL定義（memories, episodes, memory_links, coactivation_weights テーブル）
- `memory.py`: MemoryStore クラス（保存・検索・想起のメインロジック）
- `embeddings.py`: SentenceTransformer or API ベースの埋め込み生成
- `types.py`: Memory, Episode, MemoryLink, Emotion(Enum), Category(Enum) 等のデータ型
- `episode.py`: エピソード管理
- `working_memory.py`: 作業記憶バッファ
- `association.py` / `workspace.py` / `predictive.py`: 発散的想起・予測符号化

### wifi-cam-mcp のステレオビジョン

`TAPO_RIGHT_CAMERA_HOST` を設定すると、右目カメラが有効化され `see_right`, `see_both`, `both_eyes_*` 等のツールが追加される。`config.py` の `CameraConfig` でカメラごとの設定を管理。

## 環境変数

各サブプロジェクトの `.env.example` を参照。主要なもの：

- **wifi-cam-mcp**: `TAPO_CAMERA_HOST`, `TAPO_USERNAME`, `TAPO_PASSWORD`, `TAPO_ONVIF_PORT`（デフォルト2020）, `TAPO_MOUNT_MODE`（normal|ceiling）
- **memory-mcp**: `MEMORY_PG_DSN`（PostgreSQL接続文字列）, `MEMORY_EMBEDDING_MODEL`（デフォルト: intfloat/multilingual-e5-base）
- **elevenlabs-t2s-mcp**: `ELEVENLABS_API_KEY`, `GO2RTC_URL`, `GO2RTC_STREAM`
- **voicevox-mcp**: `VOICEVOX_URL`（デフォルト: http://127.0.0.1:50021）, `VOICEVOX_SPEAKER_ID`（デフォルト: 1=ずんだもん）
- **Docker Compose**: `memory-mcp/docker/` に PostgreSQL + pgvector のセットアップあり

## テスト

テストが充実しているのは **memory-mcp**、**elevenlabs-t2s-mcp**、**voicevox-mcp**。wifi-cam-mcp は物理カメラが必要なためテストなし。

```bash
# memory-mcp（PostgreSQL接続が必要）
cd memory-mcp && uv run pytest -v

# elevenlabs-t2s-mcp
cd elevenlabs-t2s-mcp && uv run pytest -v

# voicevox-mcp
cd voicevox-mcp && uv run pytest -v
```

pytest 設定: `asyncio_mode = "auto"`（pyproject.toml に定義済み）

## MCP ツール一覧

### usb-webcam-mcp（目）

| ツール | パラメータ | 説明 |
|--------|-----------|------|
| `list_cameras` | なし | 接続カメラ一覧 |
| `see` | camera_index?, width?, height? | 画像キャプチャ |

### wifi_cam_mcp（目・首・耳）

| ツール | パラメータ | 説明 |
|--------|-----------|------|
| `see` | なし | 画像キャプチャ |
| `look_left` | degrees (1-90, default: 30) | 左パン |
| `look_right` | degrees (1-90, default: 30) | 右パン |
| `look_up` | degrees (1-90, default: 20) | 上チルト |
| `look_down` | degrees (1-90, default: 20) | 下チルト |
| `look_around` | なし | 4方向スキャン |
| `camera_info` | なし | デバイス情報 |
| `camera_presets` | なし | プリセット一覧 |
| `camera_go_to_preset` | preset_id | プリセット移動 |
| `listen` | duration (1-30秒), transcribe? | 音声録音 |

#### ステレオ視覚（右目がある場合のみ）

| ツール | パラメータ | 説明 |
|--------|-----------|------|
| `see_right` | なし | 右目で撮影 |
| `see_both` | なし | 左右同時撮影 |
| `right_eye_look_*` | degrees | 右目の個別制御 |
| `both_eyes_look_*` | degrees | 両目の同時制御 |
| `get_eye_positions` | なし | 両目の角度を取得 |
| `align_eyes` | なし | 右目を左目に合わせる |
| `reset_eye_positions` | なし | 角度追跡をリセット |

### memory-mcp（脳）

| ツール | パラメータ | 説明 |
|--------|-----------|------|
| `remember` | content, emotion?, importance?, category? | 記憶保存 |
| `search_memories` | query, n_results?, filters... | 検索 |
| `recall` | context, n_results? | 文脈想起 |
| `recall_divergent` | context, n_results?, max_branches?, max_depth?, temperature?, include_diagnostics? | 発散的想起 |
| `list_recent_memories` | limit?, category_filter? | 最近一覧 |
| `get_memory_stats` | なし | 統計情報 |
| `recall_with_associations` | context, n_results?, chain_depth? | 関連記憶も含めて想起 |
| `get_memory_chain` | memory_id, depth? | 記憶の連鎖を取得 |
| `create_episode` | title, memory_ids, participants?, auto_summarize? | エピソード作成 |
| `search_episodes` | query, n_results? | エピソード検索 |
| `get_episode_memories` | episode_id | エピソード内の記憶取得 |
| `save_visual_memory` | content, image_path, camera_position, emotion?, importance? | 画像付き記憶保存 |
| `save_audio_memory` | content, audio_path, transcript, emotion?, importance? | 音声付き記憶保存 |
| `recall_by_camera_position` | pan_angle, tilt_angle, tolerance? | カメラ角度で想起 |
| `get_working_memory` | n_results? | 作業記憶を取得 |
| `refresh_working_memory` | なし | 作業記憶を更新 |
| `consolidate_memories` | window_hours?, max_replay_events?, link_update_strength? | 手動の再生・統合 |
| `get_association_diagnostics` | context, sample_size? | 連想探索の診断情報 |
| `link_memories` | source_id, target_id, link_type?, note? | 記憶をリンク |
| `get_causal_chain` | memory_id, direction?, max_depth? | 因果チェーン取得 |

**Emotion**: happy, sad, surprised, moved, excited, nostalgic, curious, neutral
**Category**: daily, philosophical, technical, memory, observation, feeling, conversation

### elevenlabs-t2s（声 - クラウド）

| ツール | パラメータ | 説明 |
|--------|-----------|------|
| `say` | text, voice_id?, model_id?, output_format?, play_audio? | ElevenLabsで音声合成して発話 |

### voicevox-mcp（声 - ローカル）

| ツール | パラメータ | 説明 |
|--------|-----------|------|
| `say` | text, speaker_id?, speed_scale?, pitch_scale?, intonation_scale?, volume_scale?, play_audio?, speaker? | VOICEVOXで音声合成して発話 |
| `list_speakers` | なし | 利用可能な話者一覧 |

### system-temperature-mcp（体温感覚）

| ツール | パラメータ | 説明 |
|--------|-----------|------|
| `get_system_temperature` | なし | システム温度 |
| `get_current_time` | なし | 現在時刻 |

## 注意事項

### WSL2 環境

1. **USB カメラ**: `usbipd` でカメラを WSL に転送する必要がある
2. **温度センサー**: WSL2 では `/sys/class/thermal/` にアクセスできない
3. **GPU**: CUDA は WSL2 でも利用可能（Whisper用）

### Tapo カメラ設定

1. Tapo アプリでローカルアカウントを作成（TP-Link アカウントではない）
2. カメラの IP アドレスを固定推奨
3. カメラ制御は ONVIF プロトコル（業界標準）を使用

### セキュリティ

- `.env` ファイルはコミットしない（.gitignore に追加済み）
- カメラパスワードは環境変数で管理
- ElevenLabs API キーは環境変数で管理
- 長期記憶は PostgreSQL に保存される（接続情報は環境変数 `MEMORY_PG_DSN` で管理）

## デバッグ

```bash
# USB カメラ確認
v4l2-ctl --list-devices

# Wi-Fi カメラ（RTSP ストリーム確認）
ffplay rtsp://username:password@192.168.1.xxx:554/stream1

# MCP サーバーログ（直接起動）
cd wifi_cam_mcp && uv run wifi-cam-mcp
```

## 外出時の構成

モバイルバッテリー + スマホテザリング + Tailscale VPN で外出散歩が可能。

```
[Tapoカメラ(肩)] ──WiFi──▶ [スマホ(テザリング)]
                                    │
                              Tailscale VPN
                                    │
                            [自宅PC(Claude Code)]
                                    │
                            [claude-code-webui]
                                    │
                            [スマホブラウザ] ◀── 操作
```

## 関連リンク

- [MCP Protocol](https://modelcontextprotocol.io/)
- [go2rtc](https://github.com/AlexxIT/go2rtc) - RTSPストリーム中継・オーディオバックチャンネル
- [claude-code-webui](https://github.com/sugyan/claude-code-webui) - Claude Code の Web UI
- [Tailscale](https://tailscale.com/) - メッシュ VPN
- [PostgreSQL](https://www.postgresql.org/) + [pgvector](https://github.com/pgvector/pgvector) + [pgroonga](https://pgroonga.github.io/) - ベクトル検索・日本語全文検索
- [OpenAI Whisper](https://github.com/openai/whisper) - 音声認識
- [ElevenLabs](https://elevenlabs.io/) - 音声合成 API
