import sqlite3
from datetime import datetime, timezone


class MemoryStore:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                scope TEXT NOT NULL,
                segment TEXT NOT NULL,
                keywords TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def remember(self, content, scope="project", segment="knowledge"):
        keywords = " ".join(content.lower().split())
        created_at = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO memories (content, scope, segment, keywords, created_at) VALUES (?, ?, ?, ?, ?)",
            (content, scope, segment, keywords, created_at),
        )
        self.conn.commit()

    def recall(self, query, scope=None, limit=5):
        words = query.lower().split()
        if not words:
            return []

        conditions = []
        params = []
        for word in words:
            conditions.append("(content LIKE ? OR keywords LIKE ?)")
            params.extend([f"%{word}%", f"%{word}%"])

        where_clause = " AND ".join(conditions)
        if scope is not None:
            where_clause += " AND scope = ?"
            params.append(scope)

        params.append(limit)

        cursor = self.conn.execute(
            f"SELECT * FROM memories WHERE {where_clause} LIMIT ?",
            params,
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
