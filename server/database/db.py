"""Logica de bază de date"""
import json
from pathlib import Path

import aiosqlite
from config.settings import DB_PATH


async def init_db():
    """Inițializează baza de date SQLite (async)"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                client TEXT,
                temperature REAL,
                humidity REAL,
                raw_data TEXT
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON sensor_data(timestamp)
        """)
        await db.commit()


async def save_sensor_data_batch(data_list: list[dict]):
    """Salvează un batch de date în SQLite (complet async)"""
    if not data_list:
        return
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executemany("""
                INSERT INTO sensor_data (timestamp, client, temperature, humidity, raw_data)
                VALUES (?, ?, ?, ?, ?)
            """, [
                (
                    d.get("timestamp"),
                    d.get("client"),
                    d.get("temperature"),
                    d.get("humidity"),
                    json.dumps(d)
                ) for d in data_list
            ])
            await db.commit()
        print(f"  💾 Salvate {len(data_list)} mesaje în SQLite")
    except Exception as e:
        print(f"  ⚠️  Eroare la salvare SQLite: {e}")


async def get_total_records() -> int:
    """Obține numărul total de înregistrări"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM sensor_data")
            row = await cursor.fetchone()
            return row[0] if row else 0
    except Exception as e:
        print(f"  ⚠️  Eroare la query: {e}")
        return 0

