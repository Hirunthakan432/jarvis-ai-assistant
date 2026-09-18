import json
import re
import time


class AuditLog:
    def __init__(self, store, retention_days=30, max_rows=10000):
        self.store, self.retention_days, self.max_rows = store, retention_days, max_rows
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY, at REAL NOT NULL, mode TEXT NOT NULL,
                action TEXT NOT NULL, status TEXT NOT NULL, risk TEXT NOT NULL,
                confirmed INTEGER NOT NULL, duration_ms INTEGER NOT NULL, parameters TEXT NOT NULL)''')

    def record(self, action, status, *, mode='LOCAL', risk='READ_ONLY', confirmed=False,
               duration_ms=0, parameters=None):
        # Never log free-form text, arguments, exception messages, URLs or tokens.
        action = action if re.fullmatch(r'[a-z_]{1,64}', action) else 'unknown_action'
        status = status if status in {'started', 'success', 'failed', 'pending', 'cancelled', 'duplicate', 'blocked'} else 'unknown'
        mode = mode if mode in {'LOCAL', 'LOCAL AI', 'CLOUD AI'} else 'LOCAL'
        risk = risk if risk in {'READ_ONLY', 'REVERSIBLE_CHANGE', 'SENSITIVE_CHANGE', 'SYSTEM_ACTION'} else 'READ_ONLY'
        safe = {k: v for k, v in (parameters or {}).items()
                if k in {'percent', 'steps'} and type(v) is int and 0 <= v <= 100}
        now = time.time()
        with self.store.connect() as db:
            db.execute('INSERT INTO audit_events(at,mode,action,status,risk,confirmed,duration_ms,parameters) VALUES (?,?,?,?,?,?,?,?)',
                       (now, mode, action, status, risk, bool(confirmed), max(0, int(duration_ms)), json.dumps(safe)))
            db.execute('DELETE FROM audit_events WHERE at < ?', (now - self.retention_days * 86400,))
            db.execute('DELETE FROM audit_events WHERE id NOT IN (SELECT id FROM audit_events ORDER BY id DESC LIMIT ?)', (self.max_rows,))

    def read(self, limit=30):
        with self.store.connect() as db:
            rows = db.execute('SELECT at,mode,action,status,risk,confirmed,duration_ms,parameters FROM audit_events ORDER BY id DESC LIMIT ?',
                              (min(200, max(1, limit)),)).fetchall()
        keys = ('at', 'mode', 'action', 'status', 'risk', 'confirmed', 'duration_ms', 'parameters')
        return [dict(zip(keys, row[:-1] + (json.loads(row[-1]),))) for row in rows]
