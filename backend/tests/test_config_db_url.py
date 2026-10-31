"""DATABASE_URL from a host such as Render must be usable by the async engine."""

from app.config import Settings


def test_render_postgres_url_gets_async_driver():
    s = Settings(DATABASE_URL="postgresql://u:p@host:5432/db")
    assert s.DATABASE_URL == "postgresql+asyncpg://u:p@host:5432/db"


def test_short_postgres_scheme_gets_async_driver():
    s = Settings(DATABASE_URL="postgres://u:p@host/db")
    assert s.DATABASE_URL == "postgresql+asyncpg://u:p@host/db"


def test_explicit_drivers_are_left_alone():
    assert Settings(DATABASE_URL="postgresql+asyncpg://u:p@h/db").DATABASE_URL == "postgresql+asyncpg://u:p@h/db"
    assert Settings(DATABASE_URL="sqlite+aiosqlite:///./x.db").DATABASE_URL == "sqlite+aiosqlite:///./x.db"
