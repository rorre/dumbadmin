from sqlite3 import Connection as SyncConnection
from aiosqlite import Connection as AsyncConnection

from passlib.hash import pbkdf2_sha256


async def get_user_from_username(db: AsyncConnection, username: str):
    cur = await db.execute(
        "SELECT username, password FROM user WHERE username = ?",
        (username,),
    )
    return await cur.fetchone()


async def register_user(db: AsyncConnection, username: str, password: str):
    """Registers user and handles all hashing asyncronously"""
    password = pbkdf2_sha256.hash(password)
    cur = await db.cursor()
    await cur.execute(
        "INSERT INTO user(username, password) VALUES (?, ?)",
        (username, password),
    )
    await db.commit()


def register_user_sync(db: SyncConnection, username: str, password: str):
    """Registers user and handles all hashing syncronously"""
    password = pbkdf2_sha256.hash(password)
    cur = db.cursor()
    cur.execute(
        "INSERT INTO user(username, password) VALUES (?, ?)",
        (username, password),
    )
    db.commit()
