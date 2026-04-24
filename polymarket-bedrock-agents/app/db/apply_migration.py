"""Apply a raw SQL migration file using the app's async DATABASE_URL (no psql required)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


def _split_statements(sql: str) -> list[str]:
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    body = "\n".join(lines).strip()
    if not body:
        return []
    return [p.strip() + ";" for p in body.split(";") if p.strip()]


async def _run(path: Path) -> int:
    sql = path.read_text(encoding="utf-8")
    stmts = _split_statements(sql)
    if not stmts:
        print("No statements found (empty file or comment-only).", file=sys.stderr)
        return 2
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.begin() as conn:
            for stmt in stmts:
                await conn.execute(text(stmt))
    finally:
        await engine.dispose()
    print(f"Applied {len(stmts)} statement(s) from {path}")
    return 0


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage: python -m app.db.apply_migration app/db/migrations/002_event_focus.sql",
            file=sys.stderr,
        )
        raise SystemExit(2)
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(_run(path)))


if __name__ == "__main__":
    main()
