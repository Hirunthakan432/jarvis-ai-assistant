"""User-managed facts, imported passages, reminders and action metadata."""
import time
from memory.structured import StructuredMemory


class AdvancedMemory:
    def __init__(self, store, *, embedding_backend='builtin', embedding_model_path=''):
        self.store = store
        self.embedding_backend, self.embedding_model_path = embedding_backend, embedding_model_path
        self._index = None
        self.retrieval_notice = ''
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS facts (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, name TEXT NOT NULL, text TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY, text TEXT NOT NULL,
                    due REAL NOT NULL, repeat_seconds INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY, at REAL NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL);
            ''')
        self.structured = StructuredMemory(store)

    def facts(self):
        return {row['key']: row['value'] for row in self.structured.read('conversation_facts')}

    def remember(self, key, value, source='user'):
        if not key or len(key) > 80 or not value or len(value) > 1000:
            raise ValueError('Memory needs a key (1–80 characters) and value (1–1000).')
        with self.store.connect() as db:
            if db.execute('SELECT COUNT(*) FROM facts').fetchone()[0] >= 50 and key not in self.facts():
                raise ValueError('Memory is full. Forget a fact before adding more.')
        return self.structured.put('conversation_facts', key, value, source)

    def forget(self, key):
        return self.structured.delete('conversation_facts', key)

    def add_document(self, name, text):
        with self.store.connect() as db:
            if db.execute('SELECT COUNT(*) FROM documents').fetchone()[0] >= 2000:
                raise ValueError('Document collection is full; remove some documents first.')
            return db.execute('INSERT INTO documents(name,text) VALUES (?,?)', (name, text)).lastrowid

    def documents(self):
        with self.store.connect() as db:
            return db.execute('SELECT id,name FROM documents ORDER BY id').fetchall()

    def read_document(self, document_id, offset=0):
        if type(offset) is not int or not 0 <= offset <= 300000:
            raise ValueError('Invalid document offset.')
        with self.store.connect() as db:
            row = db.execute('SELECT name,text FROM documents WHERE id=?', (document_id,)).fetchone()
        if row is None: raise ValueError('Imported document not found.')
        name, text = row
        return {'source': f'doc:{document_id}@{offset}', 'name': name,
                'text': text[offset:offset+10000], 'next_offset': offset+10000 if offset+10000 < len(text) else None}

    def remove_document(self, document_id):
        with self.store.connect() as db:
            changed = db.execute('DELETE FROM documents WHERE id=?', (document_id,)).rowcount
            for table in ('document_chunks', 'document_index_state'):
                if db.execute('SELECT 1 FROM sqlite_master WHERE type="table" AND name=?', (table,)).fetchone():
                    db.execute(f'DELETE FROM {table} WHERE document_id=?', (document_id,))
            return changed

    def search_documents(self, query):
        self.retrieval_notice = ''
        if self.embedding_backend != 'keyword':
            try:
                rows = self.index.search(query)
                if rows:
                    return rows
            except Exception:
                self.retrieval_notice = 'Document index unavailable — using keyword retrieval.'
        return self.keyword_search(query)

    @property
    def index(self):
        if self._index is None:
            from retrieval.index import DocumentIndex
            self._index = DocumentIndex(self.store, self.embedding_backend, self.embedding_model_path)
        return self._index

    def keyword_search(self, query):
        import re
        words = set(re.findall(r'\w+', query.lower()))
        matches = []
        with self.store.connect() as db:
            for key, name, text in db.execute('SELECT id,name,text FROM documents'):
                # Character chunks support Tamil and English without a tokenizer/model download.
                for offset in range(0, len(text), 1400):
                    passage = text[offset:offset+1800]
                    score = sum(passage.lower().count(word) for word in words)
                    if score:
                        matches.append((score, key, name, offset, passage))
        return [{'source': f'doc:{key}@{offset}', 'name': name, 'text': passage, 'retrieval': 'keyword'}
                for _, key, name, offset, passage in sorted(matches, reverse=True)[:5]]

    def remind(self, text, delay_seconds, repeat_seconds=0):
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError('Reminder text must contain 1–2000 characters.')
        if type(delay_seconds) is not int or not 1 <= delay_seconds <= 31536000:
            raise ValueError('Delay must be 1–31536000 seconds.')
        if type(repeat_seconds) is not int or (repeat_seconds != 0 and not 60 <= repeat_seconds <= 31536000):
            raise ValueError('Repeat must be 0 or 60–31536000 seconds.')
        with self.store.connect() as db:
            key = db.execute('INSERT INTO reminders(text,due,repeat_seconds) VALUES (?,?,?)',
                             (text, time.time()+delay_seconds, repeat_seconds)).lastrowid
        return f'Reminder #{key} saved. Jarvis must be running to notify you.'

    def reminders(self):
        with self.store.connect() as db:
            return [dict(zip(('id', 'text', 'due', 'repeat_seconds'), row)) for row in
                    db.execute('SELECT id,text,due,repeat_seconds FROM reminders WHERE active=1 ORDER BY due')]

    def cancel_reminder(self, key):
        with self.store.connect() as db:
            changed = db.execute('UPDATE reminders SET active=0 WHERE id=? AND active=1', (key,)).rowcount
        return 'Reminder cancelled.' if changed else 'Active reminder not found.'

    def due(self, now=None):
        now = time.time() if now is None else now
        with self.store.connect() as db:
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
        with self.store.connect() as db:
            db.execute('INSERT INTO activity(at,action,status) VALUES (?,?,?)', (time.time(), action, status))
            db.execute('DELETE FROM activity WHERE id NOT IN (SELECT id FROM activity ORDER BY id DESC LIMIT 500)')

    def activity(self):
        with self.store.connect() as db:
            return db.execute('SELECT at,action,status FROM activity ORDER BY id DESC LIMIT 30').fetchall()
