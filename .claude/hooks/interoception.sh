#!/bin/bash
# interoception.sh - AIの内受容感覚（interoception）
# UserPromptSubmitフックで毎ターン実行される
# heartbeat-daemon.sh が書き出した state file を読んでコンテキストに注入する
# 自前で計測せず、読み取り→整形→出力するだけの軽量版

STATE_FILE="/tmp/interoception_state.json"

# state file がなければフォールバック（デーモン未起動時）
if [ ! -f "$STATE_FILE" ]; then
    CURRENT_TIME=$(date '+%H:%M:%S')
    echo "[interoception] time=${CURRENT_TIME} (heartbeat daemon not running)"
    exit 0
fi

# state file から読み取って1行に整形
python3 -c "
import json, sys
try:
    with open('${STATE_FILE}') as f:
        data = json.load(f)
    now = data.get('now', {})
    trend = data.get('trend', {})
    window = data.get('window', [])

    # トレンド矢印
    arrows = {'rising': '↑', 'falling': '↓', 'stable': '→'}
    ar_arrow = arrows.get(trend.get('arousal', 'stable'), '→')
    mem_arrow = arrows.get(trend.get('mem_free', 'stable'), '→')

    # タイムスタンプから時刻部分だけ
    ts = now.get('ts', '?')
    if 'T' in ts:
        time_part = ts.split('T')[1][:8]
    else:
        time_part = ts

    parts = [
        f\"time={time_part}\",
        f\"phase={now.get('phase', '?')}\",
        f\"arousal={now.get('arousal', '?')}%({ar_arrow})\",
        f\"thermal={now.get('thermal', '?')}\",
        f\"mem_free={now.get('mem_free', '?')}%({mem_arrow})\",
        f\"uptime={now.get('uptime_min', '?')}min\",
        f\"heartbeats={len(window)}\",
    ]
    print('[interoception] ' + ' '.join(parts))
except Exception as e:
    print(f'[interoception] error reading state: {e}', file=sys.stderr)
    print('[interoception] state_file_error')
" 2>/dev/null

exit 0
