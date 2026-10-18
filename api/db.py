"""Async MySQL/TiDB access. SQL and session dates use UTC."""
import json
import os
import ssl
import asyncio
from queue import LifoQueue, Empty
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
SCHEMA = [sql.strip() for sql in (ROOT / 'api/schema.sql').read_text(encoding='utf-8').split(';') if sql.strip()]


def connection_options(database=True):
    options = dict(
        host=os.getenv('MYSQL_HOST', '127.0.0.1'),
        port=int(os.getenv('MYSQL_PORT', '3306')),
        user=os.getenv('MYSQL_USER'), password=os.getenv('MYSQL_PASSWORD'),
        charset='utf8mb4', autocommit=True, connect_timeout=15, read_timeout=60, write_timeout=60,
        init_command="SET time_zone = '+00:00'",
    )
    if database:
        options['database'] = os.getenv('MYSQL_DATABASE', 'big_rag')
    if os.getenv('MYSQL_SSL') == 'true':
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        options['ssl'] = context
    return options


def execute_sync(connection, sql, params=()):
    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute(sql, params)
        rows = list(cursor.fetchall()) if cursor.description else []
    for row in rows:
        for key, value in row.items():
            if isinstance(value, datetime) and value.tzinfo is None:
                row[key] = value.replace(tzinfo=timezone.utc)
        for key in ('metadata', 'chunks', 'prepared'):
            if isinstance(row.get(key), str):
                row[key] = json.loads(row[key])
    return rows


async def execute(connection, sql, params=()):
    return await run_in_threadpool(execute_sync, connection, sql, params)


class Database:
    def __init__(self):
        self.pool = LifoQueue()
        self.slots = None

    async def open(self):
        # PyMySQL TLS works on Windows too. Blocking socket work runs in threads.
        self.slots = asyncio.BoundedSemaphore(8)
        self.pool.put(await run_in_threadpool(pymysql.connect, **connection_options()))

    async def close(self):
        while not self.pool.empty():
            await run_in_threadpool(self.pool.get_nowait().close)

    @asynccontextmanager
    async def connection(self):
        async with self.slots:
            try:
                connection = self.pool.get_nowait()
            except Empty:
                connection = await run_in_threadpool(pymysql.connect, **connection_options())
            try:
                try:
                    await run_in_threadpool(connection.ping)
                except pymysql.MySQLError:
                    if connection.open:
                        await run_in_threadpool(connection.close)
                    connection = await run_in_threadpool(pymysql.connect, **connection_options())
                yield connection
            finally:
                if connection.open:
                    self.pool.put(connection)

    async def query(self, sql, params=()):
        async with self.connection() as connection:
            return await execute(connection, sql, params)

    @asynccontextmanager
    async def transaction(self):
        async with self.connection() as connection:
            await run_in_threadpool(connection.begin)
            try:
                yield connection
                await run_in_threadpool(connection.commit)
            except BaseException:
                await run_in_threadpool(connection.rollback)
                raise

    async def check_schema(self):
        # SELECT probes work with a CRUD-only application account too.
        for table in ('users', 'sessions', 'login_attempts', 'topics', 'documents',
                      'conversations', 'messages', 'previews', 'avatars', 'legacy_topics', 'legacy_documents'):
            await self.query(f'SELECT 1 FROM {table} LIMIT 0')
        rows = await self.query("SELECT name FROM app_settings WHERE name='legacy_owner'")
        if not rows:
            raise RuntimeError('Database is not initialized; run python -m scripts.setup_mysql')
