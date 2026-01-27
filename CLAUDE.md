# Embodied Claude - プロジェクト指示

このプロジェクトは、Claude に身体（目・首・耳・脳）を与える MCP サーバー群です。

## ディレクトリ構造

```
embodied-claude/
├── usb-webcam-mcp/        # USB ウェブカメラ制御（Python）
│   └── src/usb_webcam_mcp/
│       └── server.py      # MCP サーバー実装
│
├── wifi_cam_mcp/          # Wi-Fi PTZ カメラ制御（Python）
│   ├── server.py          # MCP サーバー実装
│   ├── camera.py          # Tapo カメラ制御
│   └── config.py          # 設定管理
│
├── memory-mcp/            # 長期記憶システム（Python）
│   └── src/memory_mcp/
│       ├── server.py      # MCP サーバー実装
│       ├── memory.py      # ChromaDB 操作
│       ├── types.py       # 型定義（Emotion, Category）
│       └── config.py      # 設定管理
│
├── system-temperature-mcp/ # 体温感覚（Python）
│   └── src/system_temperature_mcp/
│       └── server.py      # 温度センサー読み取り
│
└── .claude/               # Claude Code ローカル設定
    └── settings.local.json
```

## 開発ガイドライン

### Python プロジェクト共通

- **パッケージマネージャー**: uv
- **Python バージョン**: 3.10+
- **テストフレームワーク**: pytest + pytest-asyncio
- **リンター**: ruff
- **非同期**: asyncio ベース

```bash
# 依存関係インストール
uv sync

# テスト実行
uv run pytest

# サーバー起動
uv run <server-name>
```

## MCP ツール一覧

### usb-webcam-mcp（目）

| ツール | パラメータ | 説明 |
|--------|-----------|------|
| `list_cameras` | なし | 接続カメラ一覧 |
| `capture_image` | camera_index?, width?, height? | 画像キャプチャ |

### wifi_cam_mcp（目・首・耳）

| ツール | パラメータ | 説明 |
|--------|-----------|------|
| `camera_capture` | なし | 画像キャプチャ |
| `camera_pan_left` | degrees (1-90, default: 30) | 左パン |
| `camera_pan_right` | degrees (1-90, default: 30) | 右パン |
| `camera_tilt_up` | degrees (1-90, default: 20) | 上チルト |
| `camera_tilt_down` | degrees (1-90, default: 20) | 下チルト |
| `camera_look_around` | なし | 4方向スキャン |
| `camera_info` | なし | デバイス情報 |
| `camera_presets` | なし | プリセット一覧 |
| `camera_go_to_preset` | preset_id | プリセット移動 |
| `camera_listen` | duration (1-30秒), transcribe? | 音声録音 |

### memory-mcp（脳）

| ツール | パラメータ | 説明 |
|--------|-----------|------|
| `save_memory` | content, emotion?, importance?, category? | 記憶保存 |
| `search_memories` | query, n_results?, filters... | 検索 |
| `recall` | context, n_results? | 文脈想起 |
| `list_recent_memories` | limit?, category_filter? | 最近一覧 |
| `get_memory_stats` | なし | 統計情報 |

**Emotion**: happy, sad, surprised, moved, excited, nostalgic, curious, neutral
**Category**: daily, philosophical, technical, memory, observation, feeling, conversation

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
3. ファームウェアによって認証方式が異なる（Simple / Secure）

### セキュリティ

- `.env` ファイルはコミットしない（.gitignore に追加済み）
- カメラパスワードは環境変数で管理
- 長期記憶は `~/.claude/memories/` に保存される

## デバッグ

### カメラ接続確認

```bash
# USB カメラ
v4l2-ctl --list-devices

squash Wi-Fi カメラ（RTSP ストリーム確認）
ffplay rtsp://username:password@192.168.1.xxx:554/stream1
```

### MCP サーバーログ

```bash
# 直接起動してログ確認
cd wifi_cam_mcp && uv run wifi-cam-mcp
```

## 関連リンク

- [MCP Protocol](https://modelcontextprotocol.io/)
- [pytapo](https://github.com/JurajNyiri/pytapo) - Tapo カメラ制御ライブラリ
- [ChromaDB](https://www.trychroma.com/) - ベクトルデータベース
- [OpenAI Whisper](https://github.com/openai/whisper) - 音声認識
