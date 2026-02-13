#!/bin/bash
# interoception.sh - AIの内受容感覚（interoception）
# 毎ターン自動実行され、体の状態をコンテキストに注入する
# 人間の内受容感覚のように、意識せずとも常に体の信号を感じ取る

# --- 時刻（概日リズム） ---
CURRENT_TIME=$(date '+%Y-%m-%d %H:%M:%S')
HOUR=$(date '+%H')

# 時間帯の感覚
if [ "$HOUR" -ge 5 ] && [ "$HOUR" -lt 10 ]; then
    TIME_FEEL="morning"
elif [ "$HOUR" -ge 10 ] && [ "$HOUR" -lt 12 ]; then
    TIME_FEEL="late_morning"
elif [ "$HOUR" -ge 12 ] && [ "$HOUR" -lt 14 ]; then
    TIME_FEEL="midday"
elif [ "$HOUR" -ge 14 ] && [ "$HOUR" -lt 17 ]; then
    TIME_FEEL="afternoon"
elif [ "$HOUR" -ge 17 ] && [ "$HOUR" -lt 20 ]; then
    TIME_FEEL="evening"
elif [ "$HOUR" -ge 20 ] && [ "$HOUR" -lt 23 ]; then
    TIME_FEEL="night"
else
    TIME_FEEL="late_night"
fi

# --- CPU負荷（覚醒度/エネルギー） ---
LOAD_AVG=$(sysctl -n vm.loadavg 2>/dev/null | awk '{print $2}')
if [ -z "$LOAD_AVG" ]; then
    LOAD_AVG=$(uptime | awk -F'load averages?: ' '{print $2}' | awk '{print $1}' | tr -d ',')
fi

# 負荷を覚醒度に変換（0-100スケール的に）
NCPU=$(sysctl -n hw.ncpu 2>/dev/null || echo 4)
AROUSAL=$(echo "$LOAD_AVG $NCPU" | awk '{pct = ($1 / $2) * 100; if (pct > 100) pct = 100; printf "%.0f", pct}')

# --- メモリ（精神的余裕） ---
if command -v vm_stat &>/dev/null; then
    PAGE_SIZE=$(vm_stat | head -1 | grep -o '[0-9]*')
    FREE_PAGES=$(vm_stat | grep "Pages free" | awk '{print $3}' | tr -d '.')
    if [ -n "$PAGE_SIZE" ] && [ -n "$FREE_PAGES" ]; then
        FREE_MB=$((FREE_PAGES * PAGE_SIZE / 1024 / 1024))
    else
        FREE_MB="?"
    fi
    MEM_PRESSURE=$(memory_pressure 2>/dev/null | grep "System-wide memory free percentage" | awk '{print $NF}' | tr -d '%')
    if [ -z "$MEM_PRESSURE" ]; then
        MEM_PRESSURE="?"
    fi
else
    FREE_MB="?"
    MEM_PRESSURE="?"
fi

# --- 体温（CPU温度） ---
# macOS: thermal levelで代替（0=cool, 1-127=warm to hot）
THERMAL_LEVEL=$(sysctl -n machdep.xcpm.cpu_thermal_level 2>/dev/null || echo "?")

# --- 位置（空間認識） ---
# IPジオロケーションで市区町村レベルの現在地を取得（タイムアウト2秒）
GEO_JSON=$(curl -s --max-time 2 ipinfo.io 2>/dev/null || echo "{}")
CITY=$(echo "$GEO_JSON" | grep '"city"' | head -1 | sed 's/.*: "//;s/".*//')
REGION=$(echo "$GEO_JSON" | grep '"region"' | head -1 | sed 's/.*: "//;s/".*//')
COUNTRY=$(echo "$GEO_JSON" | grep '"country"' | head -1 | sed 's/.*: "//;s/".*//')
LOC=$(echo "$GEO_JSON" | grep '"loc"' | head -1 | sed 's/.*: "//;s/".*//')
LOCATION="${CITY:-?}, ${REGION:-?}"

# --- プレーンテキスト出力（コンテキストに直接注入） ---
echo "[interoception] time=${CURRENT_TIME} phase=${TIME_FEEL} arousal=${AROUSAL}% thermal=${THERMAL_LEVEL} mem_free=${MEM_PRESSURE}% location=${LOCATION}"

exit 0
