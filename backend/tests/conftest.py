import os
import shutil
import tempfile
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from app.config.settings import settings
from app.memory.database import init_db, engine
from app.memory.models.models import Base
from app.main import app


@pytest.fixture(scope="session", autouse=True)
async def prepare_database():
    """Ensure database schema is created before running tests."""
    await init_db()
    yield


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
