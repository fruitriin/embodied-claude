"""Pytest fixtures for Memory MCP tests (PostgreSQL backend)."""

import logging
import os
import socket
import subprocess
import time
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from dotenv import load_dotenv

from memory_mcp.config import MemoryConfig
from memory_mcp.memory import MemoryStore

load_dotenv()

logger = logging.getLogger(__name__)

_DOCKER_DIR = Path(__file__).resolve().parent.parent / "docker"

# Test-defined credentials — used both for DSN and when starting Docker
_TEST_PG_USER = "memory_mcp"
_TEST_PG_PASSWORD = "test_ci_password"
_TEST_PG_DATABASE = "embodied_claude_test"
_TEST_PG_CONTAINER = "embodied-claude-test-db"
_TEST_EMBED_CONTAINER = "embodied-claude-test-embedding"


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests that use the memory_store fixture as requiring postgres."""
    for item in items:
        if "memory_store" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.postgres)


# ── Docker auto-start helpers ──


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def _get_docker_host_port(container: str, internal_port: int) -> str | None:
    """Get the host-mapped port for a Docker container."""
    result = subprocess.run(
        ["docker", "port", container, str(internal_port)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    # Output: "0.0.0.0:14432\n[::]:14432"
    return result.stdout.strip().split("\n")[0].rsplit(":", 1)[-1]


def _wait_for_port(host: str, port: int, label: str, max_wait: int = 60):
    for i in range(max_wait // 2):
        if _is_port_open(host, port):
            logger.info("%s is ready on port %d", label, port)
            return
        time.sleep(2)
    pytest.fail(f"{label} did not become ready on port {port} within {max_wait}s")


def _wait_for_http(url: str, label: str, max_wait: int = 300):
    """Wait for an HTTP endpoint to return 200."""
    import urllib.error
    import urllib.request

    for i in range(max_wait // 5):
        try:
            urllib.request.urlopen(url, timeout=3)
            logger.info("%s is ready at %s", label, url)
            return
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(5)
    pytest.fail(f"{label} did not become ready at {url} within {max_wait}s")


_TEST_COMPOSE_FILE = _DOCKER_DIR / "docker-compose.test.yml"


def _ensure_docker_services() -> dict[str, str]:
    """Ensure Docker test services are running. Start them if needed.

    Uses docker-compose.test.yml with dedicated container names so that
    test containers don't conflict with any dev containers the user may
    already have running.

    Returns dict with 'pg_port' and 'embed_port'.
    """
    # Check if test containers are already running
    pg_port = _get_docker_host_port(_TEST_PG_CONTAINER, 5432)
    embed_port = _get_docker_host_port(_TEST_EMBED_CONTAINER, 8100)

    if pg_port and _is_port_open("localhost", int(pg_port)):
        return {"pg_port": pg_port, "embed_port": embed_port}

    # Not running — start via test compose file
    if not _TEST_COMPOSE_FILE.exists():
        pytest.fail(
            f"Docker services not running and {_TEST_COMPOSE_FILE} not found.\n"
            "Start manually: cd docker && docker compose -f docker-compose.test.yml up -d"
        )

    logger.info("Starting test Docker services from %s ...", _TEST_COMPOSE_FILE)
    subprocess.run(
        ["docker", "compose", "-f", str(_TEST_COMPOSE_FILE), "up", "-d"],
        cwd=_DOCKER_DIR,
        check=True,
    )

    # Read auto-assigned ports
    pg_port = _get_docker_host_port(_TEST_PG_CONTAINER, 5432)
    embed_port = _get_docker_host_port(_TEST_EMBED_CONTAINER, 8100)
    if not pg_port:
        pytest.fail("Failed to detect PostgreSQL port after starting Docker")

    # Wait for PostgreSQL readiness
    _wait_for_port("localhost", int(pg_port), "PostgreSQL", max_wait=60)
    for _ in range(15):
        ret = subprocess.run(
            [
                "docker", "exec", _TEST_PG_CONTAINER,
                "pg_isready", "-U", _TEST_PG_USER, "-d", _TEST_PG_DATABASE,
            ],
            capture_output=True,
        )
        if ret.returncode == 0:
            break
        time.sleep(2)

    # Wait for Embedding API (model download can be slow on first run)
    if embed_port:
        _wait_for_http(
            f"http://localhost:{embed_port}/health",
            "Embedding API",
            max_wait=300,
        )

    return {"pg_port": pg_port, "embed_port": embed_port}


# ── Fixtures ──


@pytest.fixture(scope="session")
def docker_services():
    """Session-scoped: ensure Docker services are running and return port info."""
    return _ensure_docker_services()


@pytest.fixture
def pg_dsn(docker_services) -> str:
    """Get PostgreSQL DSN for testing."""
    if os.getenv("TEST_PG_DSN"):
        return os.getenv("TEST_PG_DSN")
    port = docker_services["pg_port"]
    return (
        f"postgresql://{_TEST_PG_USER}:{_TEST_PG_PASSWORD}"
        f"@localhost:{port}/{_TEST_PG_DATABASE}"
    )


@pytest.fixture
def memory_config(pg_dsn: str, docker_services) -> MemoryConfig:
    """Create test memory config."""
    embed_url = os.getenv("TEST_EMBEDDING_API_URL")
    if not embed_url and docker_services.get("embed_port"):
        embed_url = f"http://localhost:{docker_services['embed_port']}"
    return MemoryConfig(
        pg_dsn=pg_dsn,
        pool_min_size=1,
        pool_max_size=5,
        embedding_model=os.getenv(
            "TEST_EMBEDDING_MODEL", "intfloat/multilingual-e5-base"
        ),
        embedding_api_url=embed_url,
        vector_weight=0.7,
        text_weight=0.3,
        half_life_days=30.0,
        db_path="",
        collection_name="",
    )


@pytest_asyncio.fixture
async def memory_store(memory_config: MemoryConfig) -> MemoryStore:
    """Create and connect a memory store, clean up tables between tests."""
    store = MemoryStore(memory_config)
    try:
        await store.connect()
    except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as e:
        pytest.fail(f"Failed to connect to PostgreSQL.\n\nOriginal error: {e}")

    # Clean all tables before each test
    pool = store._store._pool
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM coactivation_weights")
        await conn.execute("DELETE FROM memory_links")
        await conn.execute("DELETE FROM memories")
        await conn.execute("DELETE FROM episodes")

    yield store
    await store.disconnect()
