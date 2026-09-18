"""Transactional passage/vector index; documents remain the source of truth."""
import hashlib
import heapq
import json
import math
import threading

from retrieval.embeddings import ConceptEmbedding, SentenceEmbedding


class DocumentIndex:
    def __init__(self, store, backend='builtin', model_path=''):
        self.store, self.lock = store, threading.RLock()
        self.encoder = SentenceEmbedding(model_path) if backend == 'sentence_transformers' else ConceptEmbedding()
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS document_index_state (
                document_id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL, encoder TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS document_chunks (
                document_id INTEGER NOT NULL, offset INTEGER NOT NULL, text TEXT NOT NULL,
                vector TEXT NOT NULL, PRIMARY KEY(document_id,offset))''')
            db.execute('''CREATE TRIGGER IF NOT EXISTS invalidate_document_vectors AFTER UPDATE OF text ON documents
                BEGIN DELETE FROM document_index_state WHERE document_id=NEW.id; END''')

    def synchronize(self):
        with self.store.connect() as db:
            keys = [row[0] for row in db.execute('''SELECT d.id FROM documents d
                LEFT JOIN document_index_state s ON s.document_id=d.id
                WHERE s.document_id IS NULL OR s.encoder != ?''', (self.encoder.signature,))]
        # Read one changed document at a time, never the whole collection at once.
        for key in keys:
            with self.store.connect() as db:
                row = db.execute('SELECT text FROM documents WHERE id=?', (key,)).fetchone()
            if row is None:
                continue
            text = row[0]
            digest = hashlib.sha256(text.encode()).hexdigest()
            chunks = [(offset, text[offset:offset+1800]) for offset in range(0, len(text), 1400)]
            vectors = self.encoder.encode([chunk for _, chunk in chunks])
            if len(vectors) != len(chunks) or any(not all(math.isfinite(v) for v in vector.values()) for vector in vectors):
                raise ValueError('Invalid local embedding output.')
            with self.store.connect() as db:
                # A concurrent detach/update must not be resurrected by indexing.
                current = db.execute('SELECT text FROM documents WHERE id=?', (key,)).fetchone()
                if current is None or current[0] != text:
                    continue
                db.execute('DELETE FROM document_chunks WHERE document_id=?', (key,))
                db.executemany('INSERT INTO document_chunks VALUES (?,?,?,?)',
                    [(key, offset, passage, json.dumps(vector)) for (offset, passage), vector in zip(chunks, vectors)])
                db.execute('INSERT OR REPLACE INTO document_index_state VALUES (?,?,?)', (key, digest, self.encoder.signature))
        with self.store.connect() as db:
            db.execute('DELETE FROM document_chunks WHERE document_id NOT IN (SELECT id FROM documents)')
            db.execute('DELETE FROM document_index_state WHERE document_id NOT IN (SELECT id FROM documents)')

    def search(self, query, limit=5):
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValueError('Search needs 1–2000 characters.')
        with self.lock:
            self.synchronize()
            vector = self.encoder.encode([query])[0]
            matches = []
            with self.store.connect() as db:
                for key, name, offset, passage, raw in db.execute('''SELECT c.document_id,d.name,c.offset,c.text,c.vector
                    FROM document_chunks c JOIN documents d ON d.id=c.document_id'''):
                    stored = json.loads(raw)
                    score = sum(v * stored.get(k, 0) for k, v in vector.items())
                    if score > 0.08:
                        item = (score, key, name, offset, passage)
                        heapq.heappush(matches, item)
                        if len(matches) > limit:
                            heapq.heappop(matches)
            return [{'source': f'doc:{key}@{offset}', 'chunk': f'{key}:{offset}', 'name': name,
                     'text': passage, 'score': round(score, 4), 'retrieval': 'local_vector'}
                    for score, key, name, offset, passage in sorted(matches, reverse=True)]

    def status(self):
        with self.store.connect() as db:
            chunks = db.execute('SELECT count(*) FROM document_chunks').fetchone()[0]
            indexed = db.execute('SELECT count(*) FROM document_index_state').fetchone()[0]
        return {'backend': type(self.encoder).__name__, 'documents_indexed': indexed, 'chunks': chunks}

    def rebuild(self):
        with self.lock:
            with self.store.connect() as db:
                db.execute('DELETE FROM document_index_state')
            self.synchronize()
        return self.status()
