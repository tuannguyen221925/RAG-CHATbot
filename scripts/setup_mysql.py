"""Add missing tables; preserve managed DB credentials and existing rows."""
import asyncio
import os
import re
import secrets

import pymysql
from starlette.concurrency import run_in_threadpool

from api.db import ROOT, SCHEMA, connection_options, execute


def update_env(values):
    path = ROOT / '.env'
    content = path.read_text(encoding='utf-8') if path.exists() else ''
    for key, value in values.items():
        pattern = rf'^{key}\s*=.*$'
        replacement = f'{key}={value}'
        content = re.sub(pattern, lambda match: replacement, content, flags=re.M) if re.search(pattern, content, re.M) else content.rstrip() + '\n' + replacement + '\n'
    path.write_text(content, encoding='utf-8')


async def main():
    database = os.getenv('MYSQL_DATABASE', 'big_rag')
    if not re.fullmatch(r'[A-Za-z0-9_]+', database):
        raise ValueError('MYSQL_DATABASE khong hop le')
    managed = os.getenv('MYSQL_MANAGED') == 'true'
    connection = await run_in_threadpool(pymysql.connect, **connection_options(database=False))
    try:
        await execute(connection, f'CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        await execute(connection, f'USE `{database}`')
        for sql in SCHEMA:
            await execute(connection, sql)
        await execute(connection, "INSERT IGNORE INTO app_settings(name,value) VALUES ('legacy_owner',NULL)")
        values = {}
        if not os.getenv('RAG_SERVICE_TOKEN'):
            values['RAG_SERVICE_TOKEN'] = secrets.token_hex(32)
        if not managed:
            account, secret = 'bigrag_' + secrets.token_hex(4), secrets.token_urlsafe(32)
            await execute(connection, "CREATE USER %s@'localhost' IDENTIFIED BY %s", (account, secret))
            await execute(connection, f"GRANT SELECT,INSERT,UPDATE,DELETE ON `{database}`.* TO %s@'localhost'", (account,))
            values.update(MYSQL_USER=account, MYSQL_PASSWORD=secret)
        if values:
            update_env(values)
        print(f'Schema ready: {database}. ' + ('Managed credentials preserved.' if managed else 'CRUD account saved in .env.'))
    finally:
        connection.close()


if __name__ == '__main__':
    asyncio.run(main())
