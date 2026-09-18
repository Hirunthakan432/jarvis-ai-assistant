"""Local SQLite conversation and task storage (never committed to Git)."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from security.secrets import redact


class MemoryStore:
    def __init__(self, path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS turns (id INTEGER PRIMARY KEY, user TEXT, assistant TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, text TEXT, done INTEGER DEFAULT 0)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def history(self, limit):
        with self.connect() as db:
            rows = db.execute('SELECT user, assistant FROM (SELECT * FROM turns ORDER BY id DESC LIMIT ?) ORDER BY id', (limit,)).fetchall()
        return [message for user, reply in rows for message in (
            {'role': 'user', 'content': user}, {'role': 'assistant', 'content': reply})]

    def save_turn(self, user, reply, limit):
        user, reply = redact(user), redact(reply)
        with self.connect() as db:
            db.execute('INSERT INTO turns (user, assistant) VALUES (?, ?)', (user, reply))
            db.execute('DELETE FROM turns WHERE id NOT IN (SELECT id FROM turns ORDER BY id DESC LIMIT ?)', (limit,))

    def clear_history(self):
        with self.connect() as db:
            db.execute('DELETE FROM turns')

    def add_task(self, text):
        with self.connect() as db:
            return db.execute('INSERT INTO tasks (text) VALUES (?)', (text,)).lastrowid

    def tasks(self):
        with self.connect() as db:
            return db.execute('SELECT id, text FROM tasks WHERE done = 0 ORDER BY id').fetchall()

    def complete_task(self, task_id):
        with self.connect() as db:
            return db.execute('UPDATE tasks SET done = 1 WHERE id = ? AND done = 0', (task_id,)).rowcount == 1
