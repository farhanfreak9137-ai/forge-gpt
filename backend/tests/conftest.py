import os
import shutil
import tempfile
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

# Keep the suite away from the real database, chat sessions and browser profile. These must be set
# before app.config.settings is imported, because Settings reads the environment once at import.
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="forgeagent_test_data_"))
os.environ["FORGEAGENT_DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ["FORGEAGENT_DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TEST_DATA_DIR / 'forgeagent_test.db').as_posix()}"
os.environ["FORGEAGENT_BROWSER_PROFILE_DIR"] = str(_TEST_DATA_DIR / "browser_profile")
os.environ["FORGEAGENT_WORKSPACE_DIR"] = str(_TEST_DATA_DIR / "workspace")

from app.config.settings import settings
from app.memory.database import init_db, engine
from app.memory.models.models import Base
from app.main import app


@pytest.fixture(scope="session", autouse=True)
async def prepare_database():
    """Ensure database schema is created before running tests."""
    assert _TEST_DATA_DIR.name in settings.database_url, "tests must not touch the real database"
    await init_db()
    yield
    await engine.dispose()
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture
def temp_workspace():
    """Provides an isolated temporary workspace directory."""
    dirpath = tempfile.mkdtemp(prefix="forgeagent_test_ws_")
    yield Path(dirpath)
    shutil.rmtree(dirpath, ignore_errors=True)


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

