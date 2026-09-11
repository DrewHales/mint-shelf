"""Bounded, private local clipboard history. No network access."""
import base64
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit, unquote
from .preferences import DEFAULTS, validate

MAX_ITEM = 16 * 1024 * 1024
MAX_BYTES = 64 * 1024 * 1024
MAX_ITEMS = 200


def describe(payload):
    text = payload.get('UTF8_STRING', payload.get('text/plain;charset=utf-8', payload.get('text/plain', b''))).decode('utf-8', 'replace').strip('\x00')
    files = payload.get('x-special/gnome-copied-files', payload.get('text/uri-list', b'')).decode('utf-8', 'replace')
    if files:
        uris = [s for s in files.splitlines() if s and s not in ('cut', 'copy') and not s.startswith('#')]
        names = []
        for uri in uris:
            try:
                names.append(unquote(urlsplit(uri).path.rsplit('/', 1)[-1]) or uri)
            except ValueError:
                names.append(uri)
        return 'files', '\n'.join(names), f'{len(names)} file' + ('s' if len(names) != 1 else '')
    if any(k.startswith('image/') for k in payload):
        return 'image', text or 'Copied image', 'Image'
    try:
        parsed = urlsplit(text) if '\n' not in text and len(text) < 8192 else None
    except ValueError:
        parsed = None
    if parsed and parsed.scheme in ('http', 'https') and parsed.netloc and not any(c.isspace() for c in text):
        return 'link', text, parsed.netloc
    return 'text', text, f'{len(text):,} characters'


class Store:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        self.path = directory / 'history.sqlite3'
        self.db = sqlite3.connect(self.path)
        self.path.chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA secure_delete=ON')
        self.db.execute('CREATE TABLE IF NOT EXISTS clips (id INTEGER PRIMARY KEY, digest TEXT UNIQUE, kind TEXT, text TEXT, detail TEXT, payload TEXT, size INTEGER, pinned INTEGER DEFAULT 0, created REAL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        self.db.commit()

    def setting(self, key, default='0'):
        row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (key, value))

    def option(self, key):
        default = MAX_ITEMS if key == 'max_items' else DEFAULTS[key]
        raw = self.setting(key, str(int(default)))
        try:
            value = int(raw)
            if isinstance(default, bool):
                return bool(value) if value in (0, 1) else default
            # Unset defaults can be overridden by tests without weakening validation.
            return validate(key, value) if raw != str(int(default)) else default
        except (ValueError, TypeError):
            return default

    def save_options(self, values):
        checked = {k: validate(k, v) for k, v in values.items()}
        with self.db:
            for key, value in checked.items():
                self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, str(int(value))))
            self._prune()

    def _prune(self):
        days = self.option('retention_days')
        if days:
            self.db.execute('DELETE FROM clips WHERE pinned=0 AND created<?', (time.time() - days * 86400,))
        while True:
            count, total = self.db.execute('SELECT COUNT(*), COALESCE(SUM(size),0) FROM clips').fetchone()
            if count <= self.option('max_items') and total <= MAX_BYTES:
                break
            oldest = self.db.execute('SELECT id FROM clips WHERE pinned=0 ORDER BY created ASC LIMIT 1').fetchone()
            if not oldest:
                break
            self.db.execute('DELETE FROM clips WHERE id=?', (oldest[0],))

    def prune(self):
        with self.db:
            self._prune()

    def add(self, payload):
        payload = {k: v for k, v in payload.items() if v}
        size = sum(len(v) for v in payload.values())
        if not size or size > MAX_ITEM:
            return None
        kind, text, detail = describe(payload)
        if kind == 'image' and not self.option('capture_images'):
            return None
        if kind == 'files' and not self.option('capture_files'):
            return None
        if not text and kind == 'text':
            return None
        encoded = json.dumps({k: base64.b64encode(v).decode('ascii') for k, v in sorted(payload.items())}, sort_keys=True)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.db:
            self.db.execute('INSERT INTO clips (digest,kind,text,detail,payload,size,created) VALUES (?,?,?,?,?,?,?) ON CONFLICT(digest) DO UPDATE SET created=excluded.created', (digest, kind, text, detail, encoded, size, time.time()))
            self._prune()
        row = self.db.execute('SELECT id FROM clips WHERE digest=?', (digest,)).fetchone()
        return row[0] if row else None

    def items(self, query='', category='all'):
        rows = self.db.execute('SELECT id,kind,text,detail,pinned,created,size FROM clips ORDER BY pinned DESC,created DESC').fetchall()
        return [dict(r) for r in rows if (category == 'all' or (category == 'pinned' and r['pinned']) or r['kind'] == category) and query.casefold() in (r['text'] + ' ' + r['detail']).casefold()]

    def payload(self, clip_id):
        row = self.db.execute('SELECT payload FROM clips WHERE id=?', (clip_id,)).fetchone()
        return {k: base64.b64decode(v) for k, v in json.loads(row[0]).items()} if row else {}

    def pin(self, clip_id):
        with self.db:
            self.db.execute('UPDATE clips SET pinned=1-pinned WHERE id=?', (clip_id,))

    def delete(self, clip_id):
        with self.db:
            self.db.execute('DELETE FROM clips WHERE id=?', (clip_id,))

    def clear(self):
        with self.db:
            self.db.execute('DELETE FROM clips WHERE pinned=0')
        self.db.execute('VACUUM')
