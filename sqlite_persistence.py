import sqlite3
import json
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple

from telegram.ext import BasePersistence


class SQLitePersistence(BasePersistence):
    """
    A custom persistence class that uses SQLite to store bot data.
    This implementation is fully asynchronous to work with PTB's asyncio event loop.
    """

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath
        self.conn = None
        # Note: The connection itself is synchronous, but we'll use asyncio.to_thread for operations.
        self._connect()
        self._create_tables()

    def _connect(self):
        """Establish connection to the SQLite database."""
        self.conn = sqlite3.connect(self.filepath, check_same_thread=False)

    def _create_tables(self):
        """Create the necessary tables if they don't already exist."""
        # The `with self.conn` here is safe as it's only used for initial setup.
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS user_data (
                    user_id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS chat_data (
                    chat_id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS bot_data (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS callback_data (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
            ''')
            # Ensure default rows exist
            self.conn.execute("INSERT OR IGNORE INTO bot_data (key, data) VALUES ('bot_data', '{}')")
            self.conn.execute("INSERT OR IGNORE INTO callback_data (key, data) VALUES ('callback_data', '{}')")

    async def get_user_data(self) -> Dict[int, Dict[Any, Any]]:
        """Returns the user_data from the database."""
        def sync_get_user_data():
            try:
                cursor = self.conn.execute("SELECT user_id, data FROM user_data")
                rows = cursor.fetchall()
                
                data = {}
                for key, data_json in rows:
                    data[key] = json.loads(data_json)
                return data
            except sqlite3.Error as e:
                logging.error(f"SQLite error in get_user_data: {e}")
                return {}

        return await asyncio.to_thread(sync_get_user_data)

    async def get_chat_data(self) -> Dict[int, Dict[Any, Any]]:
        """Returns the chat_data from the database."""
        def sync_get_chat_data():
            try:
                cursor = self.conn.execute("SELECT chat_id, data FROM chat_data")
                rows = cursor.fetchall()
                
                data = {}
                for key, data_json in rows:
                    data[key] = json.loads(data_json)
                return data
            except sqlite3.Error as e:
                logging.error(f"SQLite error in get_chat_data: {e}")
                return {}

        return await asyncio.to_thread(sync_get_chat_data)

    async def get_bot_data(self) -> Dict[Any, Any]:
        """Returns the bot_data from the database."""
        def sync_get_bot_data():
            try:
                cursor = self.conn.execute("SELECT data FROM bot_data WHERE key = 'bot_data'")
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return {}
            except sqlite3.Error as e:
                logging.error(f"SQLite error in get_bot_data: {e}")
                return {}
        
        return await asyncio.to_thread(sync_get_bot_data)

    async def get_callback_data(self) -> Optional[Dict[Any, Any]]:
        """Returns the callback_data from the database."""
        def sync_get_callback_data():
            try:
                cursor = self.conn.execute("SELECT data FROM callback_data WHERE key = 'callback_data'")
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return {}
            except sqlite3.Error as e:
                logging.error(f"SQLite error in get_callback_data: {e}")
                return {}
        
        return await asyncio.to_thread(sync_get_callback_data)

    async def update_user_data(self, user_id: int, data: Dict[Any, Any]) -> None:
        """Updates a user's data in the database."""
        def sync_update_user_data():
            data_json = json.dumps(data)
            self.conn.execute(
                "INSERT OR REPLACE INTO user_data (user_id, data) VALUES (?, ?)",
                (user_id, data_json)
            )
        
        await asyncio.to_thread(sync_update_user_data)

    async def update_chat_data(self, chat_id: int, data: Dict[Any, Any]) -> None:
        """Updates a chat's data in the database."""
        def sync_update_chat_data():
            data_json = json.dumps(data)
            self.conn.execute(
                "INSERT OR REPLACE INTO chat_data (chat_id, data) VALUES (?, ?)",
                (chat_id, data_json)
            )

        await asyncio.to_thread(sync_update_chat_data)

    async def update_bot_data(self, data: Dict[Any, Any]) -> None:
        """Updates the bot's data in the database."""
        def sync_update_bot_data():
            data_json = json.dumps(data)
            self.conn.execute(
                "INSERT OR REPLACE INTO bot_data (key, data) VALUES ('bot_data', ?)",
                (data_json,)
            )
        
        await asyncio.to_thread(sync_update_bot_data)

    async def update_callback_data(self, data: Dict[Any, Any]) -> None:
        """Updates the callback_data in the database."""
        def sync_update_callback_data():
            data_json = json.dumps(data)
            self.conn.execute(
                "INSERT OR REPLACE INTO callback_data (key, data) VALUES ('callback_data', ?)",
                (data_json,)
            )

        await asyncio.to_thread(sync_update_callback_data)

    async def refresh_user_data(self, user_id: int, user_data: Dict) -> None:
        """Updates the in-memory user_data dict with data from the database."""
        def sync_refresh_user_data():
            try:
                cursor = self.conn.execute("SELECT data FROM user_data WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
            except sqlite3.Error as e:
                logging.error(f"SQLite error in refresh_user_data for user {user_id}: {e}")
                return None
        
        db_data = await asyncio.to_thread(sync_refresh_user_data)
        if db_data:
            user_data.update(db_data)

    async def refresh_chat_data(self, chat_id: int, chat_data: Dict) -> None:
        """Updates the in-memory chat_data dict with data from the database."""
        def sync_refresh_chat_data():
            try:
                cursor = self.conn.execute("SELECT data FROM chat_data WHERE chat_id = ?", (chat_id,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
            except sqlite3.Error as e:
                logging.error(f"SQLite error in refresh_chat_data for chat {chat_id}: {e}")
                return None

        db_data = await asyncio.to_thread(sync_refresh_chat_data)
        if db_data:
            chat_data.update(db_data)

    async def refresh_bot_data(self, bot_data: Dict) -> None:
        """Updates the in-memory bot_data dict with data from the database."""
        db_data = await self.get_bot_data()
        if db_data:
            bot_data.update(db_data)

    async def drop_user_data(self, user_id: int) -> None:
        """Deletes a user's data from the database."""
        def sync_drop_user_data():
            self.conn.execute("DELETE FROM user_data WHERE user_id = ?", (user_id,))
        
        await asyncio.to_thread(sync_drop_user_data)

    async def drop_chat_data(self, chat_id: int) -> None:
        """Deletes a chat's data from the database."""
        def sync_drop_chat_data():
            self.conn.execute("DELETE FROM chat_data WHERE chat_id = ?", (chat_id,))

        await asyncio.to_thread(sync_drop_chat_data)

    async def get_conversations(self, name: str) -> Dict:
        return {}

    async def update_conversation(self, name: str, key: Tuple[int, ...], new_state: Optional[object]) -> None:
        pass

    async def flush(self) -> None:
        """Commits any pending transactions to the database."""
        def sync_flush():
            if self.conn:
                self.conn.commit()
        
        await asyncio.to_thread(sync_flush)

    def close(self) -> None:
        """Closes the database connection."""
        if self.conn:
            self.conn.close()

