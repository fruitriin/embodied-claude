"""Configuration for ElevenLabs TTS MCP Server."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _detect_pulse_server() -> str | None:
    explicit = os.getenv("ELEVENLABS_PULSE_SERVER") or os.getenv("PULSE_SERVER")
    if explicit:
        return explicit
    wslg_socket = "/mnt/wslg/PulseServer"
    if os.path.exists(wslg_socket):
        return f"unix:{wslg_socket}"
    return None


@dataclass(frozen=True)
class ElevenLabsConfig:
    """ElevenLabs TTS configuration."""

    api_key: str
    voice_id: str
    model_id: str
    output_format: str
    play_audio: bool
    save_dir: str
    playback: str
    pulse_sink: str | None
    pulse_server: str | None

    @classmethod
    def from_env(cls) -> "ElevenLabsConfig":
        """Create config from environment variables."""
        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY environment variable is required")

        return cls(
            api_key=api_key,
            voice_id=os.getenv("ELEVENLABS_VOICE_ID", "uYp2UUDeS74htH10iY2e"),
            model_id=os.getenv("ELEVENLABS_MODEL_ID", "eleven_v3"),
            output_format=os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128"),
            play_audio=_parse_bool(os.getenv("ELEVENLABS_PLAY_AUDIO"), True),
            save_dir=os.getenv("ELEVENLABS_SAVE_DIR", "/tmp/elevenlabs-t2s"),
            playback=os.getenv("ELEVENLABS_PLAYBACK", "auto"),
            pulse_sink=os.getenv("ELEVENLABS_PULSE_SINK") or None,
            pulse_server=_detect_pulse_server(),
        )


@dataclass(frozen=True)
class ServerConfig:
    """MCP Server configuration."""

    name: str = "elevenlabs-t2s"
    version: str = "0.1.0"

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create config from environment variables."""
        return cls(
            name=os.getenv("MCP_SERVER_NAME", "elevenlabs-t2s"),
            version=os.getenv("MCP_SERVER_VERSION", "0.1.0"),
        )
