import sqlite3
import aiosqlite
from quart import current_app


def connect_db(url: str = ""):
    """Connects database syncronously"""
    engine = sqlite3.connect(url or current_app.config["DATABASE"])
    engine.row_factory = sqlite3.Row
    return engine


async def connect_db_async():
    """Connects database asyncronously"""
    engine = await aiosqlite.connect(current_app.config["DATABASE"])
    engine.row_factory = aiosqlite.Row
    return engine


async def get_db():
    """Get current database object"""
    if not hasattr(current_app, "db"):
        current_app.db = await connect_db_async()
    return current_app.db
