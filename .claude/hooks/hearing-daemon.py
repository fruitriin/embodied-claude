#!/usr/bin/env python3
"""
hearing-daemon.py - 常時録音デーモン

長時間稼働するバックグラウンドプロセスとして nohup で起動する。
ffmpeg segment muxer でギャップなし連続録音し、5秒ごとのチャンクを
OpenAI Whisper で文字起こしして /tmp/hearing_buffer.jsonl に追記する。
hearing-hook.sh が UserPromptSubmit のたびにバッファを読み取り、
Claude のコンテキストに [hearing] 行として注入する。

起動方法:
  nohup uv run --project /path/to/wifi-cam-mcp \\
    python hearing-daemon.py --source local --model base \\
    > /tmp/hearing-daemon.log 2>&1 &
  echo $! > /tmp/hearing-daemon.pid

停止方法:
  kill $(cat /tmp/hearing-daemon.pid)
"""

import argparse
import fcntl
import json
import logging
import os
import platform
import queue
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# ── 定数 ─────────────────────────────────────────────────────────────────────

SEGMENT_DIR = Path("/tmp/hearing_segments")
SEGMENT_LIST = SEGMENT_DIR / "list.csv"
BUFFER_FILE = Path("/tmp/hearing_buffer.jsonl")
PID_FILE = Path("/tmp/hearing-daemon.pid")

SEGMENT_SECS = 5       # 1セグメントの秒数
POLL_INTERVAL = 0.5    # セグメントリスト確認間隔（秒）
MAX_QUEUE_SIZE = 4     # Whisper が遅延した場合のキュー上限（超過分は破棄）

# Whisper ハルシネーションブラックリスト（大文字小文字無視の部分一致）
HALLUCINATION_BLACKLIST = [
    "ご視聴ありがとうございました",
    "thank you for watching",
    "チャンネル登録",
    "subscribe",
    "字幕",
    "subtitles by",
    "翻訳",
    "字幕制作",
    "ありがとうございました",
    "please subscribe",
    "like and subscribe",
]

# ── グローバル変数 ────────────────────────────────────────────────────────────

shutdown_event = threading.Event()
seg_queue: queue.Queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
logger = logging.getLogger(__name__)


# ── シグナルハンドラ ──────────────────────────────────────────────────────────


def _handle_signal(signum, frame):
    logger.info("シグナル %d を受信。シャットダウン中...", signum)
    shutdown_event.set()


# ── ffmpeg コマンド生成 ────────────────────────────────────────────────────────


def build_ffmpeg_cmd(source: str) -> list[str]:
    """ギャップなし連続録音のための ffmpeg segment muxer コマンドを生成する。"""
    system = platform.system()

    if source == "local":
        if system == "Darwin":
            input_args = ["-f", "avfoundation", "-i", ":0"]
        elif system == "Linux":
            input_args = ["-f", "alsa", "-i", "default"]
        else:
            raise RuntimeError(f"ローカルマイクに対応していないプラットフォーム: {system}")
    else:
        # source を RTSP URL として扱う
        input_args = ["-rtsp_transport", "tcp", "-i", source]

    seg_pattern = str(SEGMENT_DIR / "seg_%03d.wav")
    seg_list = str(SEGMENT_LIST)

    return [
        "ffmpeg",
        *input_args,
        "-ar", "16000",
        "-ac", "1",
        "-f", "segment",
        "-segment_time", str(SEGMENT_SECS),
        "-segment_list", seg_list,
        "-segment_list_type", "csv",
        "-segment_list_flags", "+live",
        "-y",
        seg_pattern,
    ]


# ── セグメント監視スレッド ────────────────────────────────────────────────────


def segment_watcher():
    """
    list.csv を定期的にポーリングし、完了セグメントをキューに積む。

    segment muxer は次のセグメントを開始した時点で前のセグメントのエントリを
    CSV に書き込む。つまり CSV の最終行は現在録音中のセグメントであり、
    それより前の行はすべて完了済みとなる。
    """
    known_count = 0  # すでにキューに積んだ完了セグメント数

    while not shutdown_event.is_set():
        try:
            if SEGMENT_LIST.exists():
                text = SEGMENT_LIST.read_text(encoding="utf-8").strip()
                lines = [ln for ln in text.splitlines() if ln.strip()]

                # 最終行 = 録音中。それ以前がすべて完了済み
                complete_count = max(0, len(lines) - 1)

                for i in range(known_count, complete_count):
                    seg_name = lines[i].split(",")[0]
                    seg_path = SEGMENT_DIR / seg_name
                    if seg_path.exists():
                        try:
                            seg_queue.put_nowait(seg_path)
                            logger.debug("キューに追加: %s", seg_path.name)
                        except queue.Full:
                            logger.warning(
                                "キューが満杯のためセグメントを破棄: %s", seg_path.name
                            )

                known_count = complete_count

        except Exception as e:
            logger.error("watcher エラー: %s", e)

        time.sleep(POLL_INTERVAL)


# ── 文字起こしワーカースレッド ────────────────────────────────────────────────


def transcription_worker(model_name: str):
    """
    キューからセグメントパスを取り出し、Whisper で文字起こしして JSONL バッファに追記する。
    ハルシネーションフィルタリングを適用する。
    """
    logger.info("Whisper モデル '%s' を読み込み中...", model_name)
    try:
        import whisper

        model = whisper.load_model(model_name)
        logger.info("Whisper モデル '%s' の読み込み完了", model_name)
    except ImportError:
        logger.error(
            "openai-whisper がインストールされていません。"
            " uv run --project wifi-cam-mcp python hearing-daemon.py で起動してください。"
        )
        shutdown_event.set()
        return
    except Exception as e:
        logger.error("Whisper モデルの読み込みに失敗: %s", e)
        shutdown_event.set()
        return

    seg_counter = 0
    while not shutdown_event.is_set():
        try:
            seg_path = seg_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        seg_counter += 1
        try:
            _process_segment(model, seg_path, seg_counter)
        except Exception as e:
            logger.error("%s の処理中にエラー: %s", seg_path.name, e)
        finally:
            # 処理済みセグメントファイルを削除
            try:
                seg_path.unlink(missing_ok=True)
            except Exception:
                pass
            seg_queue.task_done()


def _process_segment(model, seg_path: Path, seg_num: int) -> None:
    """1セグメントを文字起こしし、ハルシネーション判定を経てバッファに追記する。"""
    import whisper

    result = whisper.transcribe(
        model,
        str(seg_path),
        condition_on_previous_text=False,  # ループハルシネーション防止
        no_speech_threshold=0.6,           # 無音チャンクをスキップ
        compression_ratio_threshold=2.2,   # 繰り返しテキストを除去
        verbose=False,
    )

    text = result.get("text", "").strip()
    segments = result.get("segments", [])

    if not segments:
        # Whisper が無音と判定した場合はセグメントが返らない
        logger.debug("セグメント %d: 音声なし（segments が空）", seg_num)
        return

    # サブセグメント全体の no_speech_prob の最小値を採用
    no_speech_prob = min(s.get("no_speech_prob", 0.0) for s in segments)

    if not text:
        logger.debug("セグメント %d: 文字起こし結果が空", seg_num)
        return

    # ブラックリスト照合（大文字小文字無視）
    text_lower = text.lower()
    for phrase in HALLUCINATION_BLACKLIST:
        if phrase.lower() in text_lower:
            logger.debug(
                "セグメント %d: ブラックリスト一致 '%s' → 破棄", seg_num, phrase
            )
            return

    entry = {
        "ts": datetime.now().astimezone().isoformat(),
        "text": text,
        "no_speech_prob": round(no_speech_prob, 4),
        "seg": seg_num,
    }

    append_to_buffer(entry)
    logger.info(
        "セグメント %d: '%s' (no_speech_prob=%.3f)",
        seg_num,
        text[:80],
        no_speech_prob,
    )


# ── バッファ書き込み ──────────────────────────────────────────────────────────


def append_to_buffer(entry: dict) -> None:
    """排他ロックを取得してから JSONL バッファにアトミックに追記する。"""
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(BUFFER_FILE, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# ── メイン ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="embodied-claude 用 常時録音デーモン"
    )
    parser.add_argument(
        "--source",
        default="local",
        help="音声ソース: 'local'（PC マイク）または RTSP URL（デフォルト: local）",
    )
    parser.add_argument(
        "--model",
        default="base",
        help="Whisper モデルサイズ: tiny/base/small/medium（デフォルト: base）",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # ディレクトリ・ファイルの準備
    SEGMENT_DIR.mkdir(parents=True, exist_ok=True)
    # 前回起動の残骸を削除
    for stale in SEGMENT_DIR.glob("seg_*.wav"):
        stale.unlink(missing_ok=True)
    if SEGMENT_LIST.exists():
        SEGMENT_LIST.unlink()
    BUFFER_FILE.touch(exist_ok=True)

    PID_FILE.write_text(str(os.getpid()))
    logger.info(
        "hearing daemon 起動 (PID=%d, source=%s, model=%s)",
        os.getpid(),
        args.source,
        args.model,
    )

    # バックグラウンドスレッドを起動
    watcher = threading.Thread(target=segment_watcher, daemon=True, name="watcher")
    watcher.start()

    transcriber = threading.Thread(
        target=transcription_worker,
        args=(args.model,),
        daemon=True,
        name="transcription",
    )
    transcriber.start()

    # メインループ: ffmpeg を起動し、異常終了時は再起動する
    cmd = build_ffmpeg_cmd(args.source)
    logger.info("ffmpeg 起動: %s", " ".join(cmd))

    while not shutdown_event.is_set():
        ffmpeg_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        while not shutdown_event.is_set():
            try:
                ffmpeg_proc.wait(timeout=1.0)
                # ffmpeg が予期せず終了した
                stderr_tail = ffmpeg_proc.stderr.read().decode(errors="replace")[-300:]
                logger.error("ffmpeg が予期せず終了:\n%s", stderr_tail)
                break  # 再起動ループへ
            except subprocess.TimeoutExpired:
                continue  # 正常稼働中

        if shutdown_event.is_set():
            ffmpeg_proc.terminate()
            try:
                ffmpeg_proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                ffmpeg_proc.kill()
            break

        logger.info("2秒後に ffmpeg を再起動します...")
        time.sleep(2)

    # シャットダウン処理
    logger.info("スレッドをシャットダウン中...")
    shutdown_event.set()
    watcher.join(timeout=5.0)
    transcriber.join(timeout=30.0)  # 処理中の文字起こしが完了するまで待機
    PID_FILE.unlink(missing_ok=True)
    logger.info("hearing daemon 停止")


if __name__ == "__main__":
    main()
