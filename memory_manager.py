import sqlite3
import os
import json
from typing import List, Dict

class MemoryManager:
    def __init__(self, db_path: str = "clawyu_memory.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Initializes the SQLite database with necessary tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def get_or_create_session(self, session_id: str):
        """Ensures a session exists in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO sessions (session_id) VALUES (?)', (session_id,))
        conn.commit()
        conn.close()

    def add_message(self, session_id: str, role: str, content: str):
        """Adds a message to the conversation history."""
        self.get_or_create_session(session_id)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)',
            (session_id, role, content)
        )
        conn.commit()
        conn.close()

    def get_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Retrieves the recent conversation history for a session."""
        conn = sqlite3.connect(self.db_path)
        # Using dict factory for easier conversion to python dicts
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT role, content FROM messages 
            WHERE session_id = ? 
            ORDER BY created_at ASC 
            LIMIT ?
        ''', (session_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{"role": row["role"], "content": row["content"]} for row in rows]

# Singleton instance
memory_manager = MemoryManager()
