"""Restore users' search caches from canonical PDFs/vectors in MySQL."""
import asyncio

from api.db import Database
from api.library import restore_library
from api.rag_service import RagService


async def main():
    db, rag = Database(), RagService()
    try:
        await db.open()
        await restore_library(db, rag)
    finally:
        await rag.close()
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())
