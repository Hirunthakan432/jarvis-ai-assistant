import sqlite3
import tempfile
from pathlib import Path
import unittest
from memory.store import MemoryStore


class ConnectionTests(unittest.TestCase):
    def test_connection_closes_and_failed_transaction_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / 'memory.sqlite3')
            with self.assertRaises(RuntimeError):
                with store.connect() as db:
                    db.execute("INSERT INTO tasks (text) VALUES ('unfinished')")
                    raise RuntimeError('abort')
            with self.assertRaises(sqlite3.ProgrammingError):
                db.execute('SELECT 1')
            self.assertEqual(store.tasks(), [])
            store.add_task('saved')
            self.assertEqual(store.tasks()[0][1], 'saved')
