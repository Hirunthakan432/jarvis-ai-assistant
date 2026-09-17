"""Additive, transactional memory metadata. Legacy tables remain readable."""
import time
from security.secrets import reject_credentials

CATEGORIES = {'user_preferences', 'assistant_settings', 'device_aliases',
              'study_preferences', 'project_context', 'conversation_facts'}
SOURCES = {'user', 'deterministic', 'learned', 'semantic', 'local_llm', 'cloud_llm', 'migration'}


class StructuredMemory:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS memory_records (
                category TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                created_at REAL, updated_at REAL NOT NULL, source TEXT NOT NULL,
                PRIMARY KEY(category,key))''')
            # Unknown historical timestamps are NULL rather than invented dates.
            db.execute('''INSERT OR IGNORE INTO memory_records
                SELECT 'conversation_facts', key, value, NULL, ?, 'migration' FROM facts''', (time.time(),))
            # Reconcile edits made by an older Jarvis after a rollback.
            db.execute('''UPDATE memory_records SET value=(SELECT value FROM facts WHERE key=memory_records.key),
                updated_at=?, source='migration' WHERE category='conversation_facts' AND key IN
                (SELECT key FROM facts) AND value != (SELECT value FROM facts WHERE key=memory_records.key)''', (time.time(),))
            db.execute("DELETE FROM memory_records WHERE category='conversation_facts' AND key NOT IN (SELECT key FROM facts)")

    @staticmethod
    def validate(category, key, value=None, source='user'):
        if category not in CATEGORIES or source not in SOURCES:
            raise ValueError('Unknown memory category or source.')
        if not isinstance(key, str) or not key.strip() or len(key) > 80:
            raise ValueError('Memory key must contain 1–80 characters.')
        if value is not None:
            if not isinstance(value, str) or not value.strip() or len(value) > 1000:
                raise ValueError('Memory value must contain 1–1000 characters.')
            reject_credentials(key, value)

    def put(self, category, key, value, source='user', *, create_only=False, update_only=False):
        self.validate(category, key, value, source)
        now = time.time()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            found = db.execute('SELECT 1 FROM memory_records WHERE category=? AND key=?', (category, key)).fetchone()
            if create_only and found:
                raise ValueError('Memory already exists. Use update.')
            if update_only and not found:
                raise ValueError('Memory not found. Use create.')
            if not found and db.execute('SELECT COUNT(*) FROM memory_records').fetchone()[0] >= 500:
                raise ValueError('Structured memory is full (500 records).')
            db.execute('''INSERT INTO memory_records VALUES (?,?,?,?,?,?)
                ON CONFLICT(category,key) DO UPDATE SET value=excluded.value,
                updated_at=excluded.updated_at, source=excluded.source''', (category, key, value, now, now, source))
            if category == 'conversation_facts':
                db.execute('INSERT INTO facts VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))
        return 'Memory saved.'

    def read(self, category=None, key=None):
        if category is not None and category not in CATEGORIES:
            raise ValueError('Unknown memory category.')
        with self.store.connect() as db:
            rows = db.execute('''SELECT category,key,value,created_at,updated_at,source FROM memory_records
                WHERE (? IS NULL OR category=?) AND (? IS NULL OR key=?) ORDER BY category,key''',
                (category, category, key, key)).fetchall()
        result = []
        for row in rows:
            try:
                reject_credentials(row[1], row[2])
            except ValueError:
                # Keep old data intact for rollback; never export detected credentials.
                continue
            result.append(dict(zip(('category', 'key', 'value', 'created_at', 'updated_at', 'source'), row)))
        return result

    def delete(self, category, key):
        self.validate(category, key)
        with self.store.connect() as db:
            changed = db.execute('DELETE FROM memory_records WHERE category=? AND key=?', (category, key)).rowcount
            if category == 'conversation_facts':
                db.execute('DELETE FROM facts WHERE key=?', (key,))
        return 'Memory forgotten.' if changed else 'Memory key not found.'
