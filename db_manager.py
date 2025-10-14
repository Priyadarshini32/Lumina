import sqlite3
import json
from datetime import datetime

DATABASE_NAME = "agent_data.db"

def initialize_db():
    """Initializes the SQLite database and creates the conversations table."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_input TEXT NOT NULL,
            agent_response TEXT,
            tools_used TEXT,
            memory_summary TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_conversation_data(user_input: str, agent_response: str, tools_used: list, memory_summary: dict):
    """Saves a single conversation turn to the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    
    # Convert lists/dicts to JSON strings for storage
    tools_used_json = json.dumps(tools_used)
    memory_summary_json = json.dumps(memory_summary)

    cursor.execute("""
        INSERT INTO conversations (timestamp, user_input, agent_response, tools_used, memory_summary)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp, user_input, agent_response, tools_used_json, memory_summary_json))
    conn.commit()
    conn.close()

def get_all_conversations():
    """Retrieves all conversations from the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, timestamp, user_input, agent_response, tools_used, memory_summary FROM conversations ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    conn.close()
    
    conversations = []
    for row in rows:
        conv_id, timestamp, user_input, agent_response, tools_used_json, memory_summary_json = row
        conversations.append({
            "id": conv_id,
            "timestamp": timestamp,
            "user_input": user_input,
            "agent_response": agent_response,
            "tools_used": json.loads(tools_used_json) if tools_used_json else [],
            "memory_summary": json.loads(memory_summary_json) if memory_summary_json else {}
        })
    return conversations
