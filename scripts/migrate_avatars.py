"""Add avatar storage to an existing database with temporary admin credentials."""
import asyncio
import os
import re

import pymysql
from starlette.concurrency import run_in_threadpool

from api.db import SCHEMA, connection_options, execute


async def main():
    options = connection_options()
    database = options['database']
    if not re.fullmatch(r'[A-Za-z0-9_]+', database):
        raise ValueError('Invalid database name')
    options.update(user=os.getenv('MYSQL_ADMIN_USER') or os.getenv('MYSQL_USER'), password=os.getenv('MYSQL_ADMIN_PASSWORD') or os.getenv('MYSQL_PASSWORD'))
    connection = await run_in_threadpool(pymysql.connect, **options)
    try:
        await execute(connection, next(sql for sql in SCHEMA if sql.startswith('CREATE TABLE IF NOT EXISTS avatars ')))
        print(f'Avatar storage ready: {database}')
    finally:
        connection.close()


if __name__ == '__main__':
    asyncio.run(main())
