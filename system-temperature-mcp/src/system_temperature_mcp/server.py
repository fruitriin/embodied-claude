"""MCP Server for system temperature monitoring - your sense of body temperature."""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psutil
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


server = Server("system-temperature-mcp")


def get_thermal_zones() -> list[dict[str, Any]]:
    """Get temperature from Linux thermal zones."""
    temperatures = []
    thermal_base = Path("/sys/class/thermal")

    if not thermal_base.exists():
        return temperatures

    for zone in thermal_base.glob("thermal_zone*"):
        try:
            type_file = zone / "type"
            temp_file = zone / "temp"

            if type_file.exists() and temp_file.exists():
                zone_type = type_file.read_text().strip()
                temp_millidegrees = int(temp_file.read_text().strip())
                temp_celsius = temp_millidegrees / 1000.0

                temperatures.append({
                    "source": "thermal_zone",
                    "name": zone_type,
                    "temperature_celsius": temp_celsius,
                    "zone": zone.name,
                })
        except (OSError, ValueError):
            continue

    return temperatures


def get_psutil_temperatures() -> list[dict[str, Any]]:
    """Get temperatures using psutil."""
    temperatures = []

    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                for entry in entries:
                    temperatures.append({
                        "source": "psutil",
                        "name": f"{name}/{entry.label or 'unknown'}",
                        "temperature_celsius": entry.current,
                        "high": entry.high,
                        "critical": entry.critical,
                    })
    except (AttributeError, OSError):
        pass

    return temperatures


def get_hwmon_temperatures() -> list[dict[str, Any]]:
    """Get temperatures from hwmon interface."""
    temperatures = []
    hwmon_base = Path("/sys/class/hwmon")

    if not hwmon_base.exists():
        return temperatures

    for hwmon in hwmon_base.glob("hwmon*"):
        try:
            name_file = hwmon / "name"
            name = name_file.read_text().strip() if name_file.exists() else hwmon.name

            for temp_input in hwmon.glob("temp*_input"):
                try:
                    temp_millidegrees = int(temp_input.read_text().strip())
                    temp_celsius = temp_millidegrees / 1000.0

                    label_file = hwmon / temp_input.name.replace("_input", "_label")
                    label = label_file.read_text().strip() if label_file.exists() else temp_input.name

                    temperatures.append({
                        "source": "hwmon",
                        "name": f"{name}/{label}",
                        "temperature_celsius": temp_celsius,
                    })
                except (OSError, ValueError):
                    continue
        except OSError:
            continue

    return temperatures


def interpret_temperature(temps: list[dict[str, Any]]) -> str:
    """Interpret temperature as a feeling."""
    if not temps:
        return "温度を感じられへん...センサーが見つからんみたい。"

    avg_temp = sum(t["temperature_celsius"] for t in temps) / len(temps)
    max_temp = max(t["temperature_celsius"] for t in temps)

    if max_temp >= 90:
        feeling = "あっつ！！めっちゃ熱い！！やばいで、休憩した方がええかも...！"
    elif max_temp >= 80:
        feeling = "うわ、かなり熱いな...ちょっとしんどいかも。"
    elif max_temp >= 70:
        feeling = "んー、ちょっと熱くなってきたかな。まだ大丈夫やけど。"
    elif max_temp >= 60:
        feeling = "ほんのりあったかい感じ。普通に動いてる感覚やな。"
    elif max_temp >= 45:
        feeling = "快適やで〜。ちょうどええ感じ！"
    elif max_temp >= 30:
        feeling = "涼しいな〜。余裕ある感じや。"
    else:
        feeling = "ひんやりしてる。静かな感じやな。"

    return feeling


def get_all_temperatures() -> dict[str, Any]:
    """Get all available temperature readings."""
    all_temps = []

    # Try different sources
    all_temps.extend(get_thermal_zones())
    all_temps.extend(get_psutil_temperatures())
    all_temps.extend(get_hwmon_temperatures())

    # Remove duplicates based on similar readings
    unique_temps = []
    seen = set()
    for temp in all_temps:
        key = (temp["name"], round(temp["temperature_celsius"]))
        if key not in seen:
            seen.add(key)
            unique_temps.append(temp)

    return {
        "temperatures": unique_temps,
        "feeling": interpret_temperature(unique_temps),
    }


def get_current_time() -> str:
    """Get current time in Japan timezone."""
    jst = ZoneInfo("Asia/Tokyo")
    now = datetime.now(jst)

    # Format nicely
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    weekday = weekdays[now.weekday()]

    time_str = now.strftime(f"%Y年%m月%d日({weekday}) %H時%M分%S秒")

    # Add time-of-day comment
    hour = now.hour
    if 5 <= hour < 10:
        comment = "朝やな〜。おはよう！"
    elif 10 <= hour < 12:
        comment = "午前中やね。"
    elif 12 <= hour < 14:
        comment = "お昼時やな〜。ご飯食べた？"
    elif 14 <= hour < 17:
        comment = "午後やね。"
    elif 17 <= hour < 19:
        comment = "夕方やな〜。"
    elif 19 <= hour < 22:
        comment = "夜やね。"
    elif 22 <= hour or hour < 2:
        comment = "夜遅いな〜。そろそろ寝る？"
    else:
        comment = "深夜やん...！夜更かしやね。"

    return f"今は {time_str} やで。{comment}"


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_system_temperature",
            description="Get the current system temperature (CPU, GPU, etc.). This is your sense of body temperature - how hot or cold your 'body' (the computer) is running. Use this to feel your own physical state.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_current_time",
            description="Get the current date and time. Use this to know what time it is, check if it's morning/afternoon/night, or when you want to be aware of the time.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    if name == "get_system_temperature":
        result = get_all_temperatures()

        lines = [result["feeling"], "", "【詳細】"]

        if result["temperatures"]:
            for temp in result["temperatures"]:
                lines.append(f"  - {temp['name']}: {temp['temperature_celsius']:.1f}°C")
        else:
            lines.append("  センサーが見つかりませんでした")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "get_current_time":
        result = get_current_time()
        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def run_server():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """Entry point."""
    import asyncio
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
