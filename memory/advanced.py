"""User-managed facts, imported passages, reminders and action metadata."""
import time
from contextlib import closing


class AdvancedMemory:
    def __init__(self, store):
        self.store = store
        with closing(store.connect()) as db, db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS facts (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, name TEXT NOT NULL, text TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY, text TEXT NOT NULL,
                    due REAL NOT NULL, repeat_seconds INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY, at REAL NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL);
            ''')

    def facts(self):
        with closing(self.store.connect()) as db:
            return dict(db.execute('SELECT key, value FROM facts ORDER BY key').fetchall())

    def remember(self, key, value):
        if not key or len(key) > 80 or not value or len(value) > 1000:
            raise ValueError('Memory needs a key (1–80 characters) and value (1–1000).')
        with closing(self.store.connect()) as db, db:
            if db.execute('SELECT COUNT(*) FROM facts').fetchone()[0] >= 50 and key not in self.facts():
                raise ValueError('Memory is full. Forget a fact before adding more.')
            db.execute('INSERT INTO facts VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))
        return 'Memory saved.'

    def forget(self, key):
        with closing(self.store.connect()) as db, db:
            changed = db.execute('DELETE FROM facts WHERE key=?', (key,)).rowcount
        return 'Memory forgotten.' if changed else 'Memory key not found.'

    def add_document(self, name, text):
        with closing(self.store.connect()) as db, db:
            if db.execute('SELECT COUNT(*) FROM documents').fetchone()[0] >= 2000:
                raise ValueError('Document collection is full; remove some documents first.')
            return db.execute('INSERT INTO documents(name,text) VALUES (?,?)', (name, text)).lastrowid

    def documents(self):
        with closing(self.store.connect()) as db:
            return db.execute('SELECT id,name FROM documents ORDER BY id').fetchall()

    def read_document(self, document_id, offset=0):
        if type(offset) is not int or not 0 <= offset <= 300000:
            raise ValueError('Invalid document offset.')
        with closing(self.store.connect()) as db:
            row = db.execute('SELECT name,text FROM documents WHERE id=?', (document_id,)).fetchone()
        if row is None: raise ValueError('Imported document not found.')
        name, text = row
        return {'source': f'doc:{document_id}@{offset}', 'name': name,
                'text': text[offset:offset+10000], 'next_offset': offset+10000 if offset+10000 < len(text) else None}

    def remove_document(self, document_id):
        with closing(self.store.connect()) as db, db:
            return db.execute('DELETE FROM documents WHERE id=?', (document_id,)).rowcount

    def search_documents(self, query):
        import re
        words = set(re.findall(r'\w+', query.lower()))
        matches = []
        with closing(self.store.connect()) as db:
            for key, name, text in db.execute('SELECT id,name,text FROM documents'):
                # Character chunks support Tamil and English without a tokenizer/model download.
                for offset in range(0, len(text), 1400):
                    passage = text[offset:offset+1800]
                    score = sum(passage.lower().count(word) for word in words)
                    if score:
                        matches.append((score, key, name, offset, passage))
        return [{'source': f'doc:{key}@{offset}', 'name': name, 'text': passage}
                for _, key, name, offset, passage in sorted(matches, reverse=True)[:5]]

    def remind(self, text, delay_seconds, repeat_seconds=0):
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError('Reminder text must contain 1–2000 characters.')
        if type(delay_seconds) is not int or not 1 <= delay_seconds <= 31536000:
            raise ValueError('Delay must be 1–31536000 seconds.')
        if type(repeat_seconds) is not int or (repeat_seconds != 0 and not 60 <= repeat_seconds <= 31536000):
            raise ValueError('Repeat must be 0 or 60–31536000 seconds.')
        with closing(self.store.connect()) as db, db:
            key = db.execute('INSERT INTO reminders(text,due,repeat_seconds) VALUES (?,?,?)',
                             (text, time.time()+delay_seconds, repeat_seconds)).lastrowid
        return f'Reminder #{key} saved. Jarvis must be running to notify you.'

    def reminders(self):
        with closing(self.store.connect()) as db:
            return [dict(zip(('id', 'text', 'due', 'repeat_seconds'), row)) for row in
                    db.execute('SELECT id,text,due,repeat_seconds FROM reminders WHERE active=1 ORDER BY due')]

    def cancel_reminder(self, key):
        with closing(self.store.connect()) as db, db:
            changed = db.execute('UPDATE reminders SET active=0 WHERE id=? AND active=1', (key,)).rowcount
        return 'Reminder cancelled.' if changed else 'Active reminder not found.'

    def due(self, now=None):
        now = time.time() if now is None else now
        with closing(self.store.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute('SELECT id,text,due,repeat_seconds FROM reminders WHERE active=1 AND due<=?', (now,)).fetchall()
            for key, text, due, repeat in rows:
                if repeat:
                    next_due = due + (int((now-due)//repeat)+1)*repeat
                    db.execute('UPDATE reminders SET due=? WHERE id=?', (next_due, key))
                else:
                    db.execute('UPDATE reminders SET active=0 WHERE id=?', (key,))
        return [(key, text) for key, text, _, _ in rows]

    def audit(self, action, status):
        with closing(self.store.connect()) as db, db:
            db.execute('INSERT INTO activity(at,action,status) VALUES (?,?,?)', (time.time(), action, status))
            db.execute('DELETE FROM activity WHERE id NOT IN (SELECT id FROM activity ORDER BY id DESC LIMIT 500)')

    def activity(self):
        with closing(self.store.connect()) as db:
            return db.execute('SELECT at,action,status FROM activity ORDER BY id DESC LIMIT 30').fetchall()
