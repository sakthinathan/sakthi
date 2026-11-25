import os
import pytest
import pytest_asyncio
import asyncio

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("AUTH_SECRET_KEY", "test-auth-secret-key-minimum-32-characters-long!")
os.environ.setdefault("INITIAL_ADMIN_PASSWORD", "UtsavOps2026!Secure")

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def test_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

@pytest_asyncio.fixture
async def client(test_session):
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def auth_client(client, test_session):
    from app.routers.auth import seed_initial_admin
    from app.utils.security import create_access_token
    operator = await seed_initial_admin(test_session)
    token = create_access_token({"sub": operator.id, "email": operator.email, "role": operator.role})
    client.headers["Authorization"] = f"Bearer {token}"
    return client
