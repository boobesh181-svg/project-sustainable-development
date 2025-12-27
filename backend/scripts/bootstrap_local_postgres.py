"""Bootstrap local Postgres for the MRV backend.

Creates/updates the `windsurf` role and `windsurf` database using a local admin DSN.

Usage (PowerShell):
  $env:PG_ADMIN_DSN = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
  python scripts/bootstrap_local_postgres.py
"""

import asyncio
import os

import re

import asyncpg


ADMIN_DSN_DEFAULT = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
TARGET_ROLE = os.environ.get("PG_APP_USER", "windsurf")
TARGET_PASSWORD = os.environ.get("PG_APP_PASSWORD", "windsurf_pass")
TARGET_DB = os.environ.get("PG_APP_DB", "windsurf")


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(name: str) -> str:
    """Return a safely-quoted SQL identifier.

    We keep it strict to avoid SQL injection in bootstrap commands.
    """

    if not _IDENT_RE.match(name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return '"' + name + '"'


def _literal(text: str) -> str:
    """Return a safely-quoted SQL string literal."""

    return "'" + text.replace("'", "''") + "'"


async def main() -> None:
    admin_dsn = os.environ.get("PG_ADMIN_DSN", ADMIN_DSN_DEFAULT)

    conn = await asyncpg.connect(dsn=admin_dsn)
    try:
        role_exists = await conn.fetchval(
            "select 1 from pg_roles where rolname = $1", TARGET_ROLE
        )
        role_ident = _ident(TARGET_ROLE)
        db_ident = _ident(TARGET_DB)
        pw_lit = _literal(TARGET_PASSWORD)

        if role_exists:
            await conn.execute(f"alter role {role_ident} with login password {pw_lit}")
            print(f"Updated role: {TARGET_ROLE}")
        else:
            await conn.execute(f"create role {role_ident} with login password {pw_lit}")
            print(f"Created role: {TARGET_ROLE}")

        db_exists = await conn.fetchval(
            "select 1 from pg_database where datname = $1", TARGET_DB
        )
        if not db_exists:
            await conn.execute(
                f"create database {db_ident} owner {role_ident}"
            )
            print(f"Created database: {TARGET_DB}")
        else:
            print(f"Database already exists: {TARGET_DB}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
