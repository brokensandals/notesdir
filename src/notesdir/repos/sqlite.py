from collections import namedtuple
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Optional, Set, List
from notesdir.models import FileInfo, FileEditCmd
from notesdir.repos.direct import DirectRepo


SQL_CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL,
    existent BOOLEAN,
    stat_ctime INTEGER,
    stat_mtime INTEGER,
    stat_size INTEGER,
    title TEXT,
    created TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS files_index_path ON files (path);

CREATE TABLE IF NOT EXISTS file_tags (
    file_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY(file_id) REFERENCES files(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS file_tags_index_file_id_tag ON file_tags (file_id, tag);
CREATE INDEX IF NOT EXISTS file_tags_index_tag ON file_tags (tag);

CREATE TABLE IF NOT EXISTS file_refs (
    id INTEGER PRIMARY KEY,
    referrer_id INTEGER NOT NULL,
    referent_id INTEGER,
    ref TEXT NOT NULL,
    FOREIGN KEY(referrer_id) REFERENCES files(id),
    FOREIGN KEY(referent_id) REFERENCES files(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS file_refs_referrer_id_ref ON file_refs (referrer_id, ref);
CREATE INDEX IF NOT EXISTS file_refs_referrer_id_referent_id ON file_refs (referrer_id, referent_id);
CREATE INDEX IF NOT EXISTS file_refs_referent_id_referrer_id ON file_refs (referent_id, referrer_id);
"""

SQL_CLEAR = """
DELETE FROM files;
DELETE FROM file_tags;
DELETE_FROM file_refs;
"""


SQL_ALL_FOR_REFRESH = 'SELECT id, path, stat_ctime, stat_mtime, stat_size FROM files'
SqlAllForRefreshRow = namedtuple('SqlAllForRefreshRow', ['id', 'path', 'stat_ctime', 'stat_mtime', 'stat_size'])

SQL_INSERT_FILE = ('INSERT INTO files (path, existent, stat_ctime, stat_mtime, stat_size, title, created)'
                   ' VALUES (?, ?, ?, ?, ?, ?, ?)')
SqlInsertFileRow = namedtuple('SqlInsertFileRow', ['path', 'existent', 'stat_ctime', 'stat_mtime', 'stat_size',
                                                   'title', 'created'])

SQL_UPDATE_FILE = ('UPDATE files SET existent = ?, stat_ctime = ?, stat_mtime = ?, stat_size = ?,'
                   ' title = ?, created = ?'
                   ' WHERE id = ?')
SqlUpdateFileRow = namedtuple('SqlUpdateFileRow', ['existent', 'stat_ctime', 'stat_mtime', 'stat_size',
                                                   'title', 'created', 'id'])


class SqliteRepo(DirectRepo):
    def __init__(self, config: dict):
        super().__init__(config)
        if 'cache' not in config:
            raise ValueError('repo config is missing "cache", which must be the path at which to store the sqlite3 db')
        self.db_path = config['cache']
        self.connection = None
        self.connect()
        self.refresh()

    def connect(self):
        self.connection = sqlite3.connect(self.db_path)
        self.connection.executescript(SQL_CREATE_SCHEMA)

    def refresh(self):
        cursor = self.connection.cursor()
        cursor.execute(SQL_ALL_FOR_REFRESH)
        prior_rows = (SqlAllForRefreshRow(*r) for r in cursor.fetchall())
        prior_rows_by_path = {r.path: r for r in prior_rows}

        ids_by_path = {}
        refs_to_add = []

        for path in self._paths():
            pathstr = str(path)
            stat = path.stat()
            row = prior_rows_by_path.get(pathstr)
            if (row and row.stat_ctime == stat.st_ctime
                    and row.stat_mtime == stat.st_mtime
                    and row.stat_size == stat.st_size):
                continue
            info = super().info(path)
            if row:
                file_id = row.id
                cursor.execute('DELETE FROM file_tags WHERE file_id = ?', (file_id,))
                cursor.execute('DELETE FROM file_refs WHERE referrer_id = ?', (file_id,))
                updrow = SqlUpdateFileRow(id=file_id,
                                          existent=path.is_file(),
                                          stat_ctime=stat.st_ctime,
                                          stat_mtime=stat.st_mtime,
                                          stat_size=stat.st_size,
                                          title=info.title,
                                          created=info.created)
                cursor.execute(SQL_UPDATE_FILE, updrow)
            else:
                newrow = SqlInsertFileRow(path=pathstr,
                                          existent=path.is_file(),
                                          stat_ctime=stat.st_ctime,
                                          stat_mtime=stat.st_mtime,
                                          stat_size=stat.st_size,
                                          title=info.title,
                                          created=info.created)
                cursor.execute(SQL_INSERT_FILE, newrow)
                file_id = cursor.lastrowid
            cursor.executemany('INSERT INTO file_tags (file_id, tag) VALUES (?, ?)',
                               ((file_id, t) for t in info.tags))
            ids_by_path[pathstr] = file_id
            for referent_path, refs in info.path_refs().items():
                refs_to_add.append((file_id, str(referent_path) if referent_path else None, refs))

        for referrer_id, referent_path, refs in refs_to_add:
            referent_id = None
            if referent_path:
                referent_id = ids_by_path.get(referent_path)
                if not referent_id:
                    prior_row = prior_rows_by_path.get(referent_path)
                    if prior_row:
                        referent_id = prior_row.id
                if not referent_id:
                    cursor.execute('INSERT INTO files (path, existent) VALUES (?, FALSE)', (referent_path,))
                    referent_id = cursor.lastrowid
                    ids_by_path[referent_path] = referent_id
            cursor.executemany('INSERT INTO file_refs (referrer_id, referent_id, ref)'
                               ' VALUES (?, ?, ?)',
                               ((referrer_id, referent_id, ref) for ref in refs))

        self.connection.commit()

    def info(self, path: Path) -> Optional[FileInfo]:
        cursor = self.connection.cursor()
        cursor.execute('SELECT id, title, created FROM files WHERE path = ? AND existent = TRUE',
                       (str(path.resolve()),))
        file_row = cursor.fetchone()
        if not file_row:
            return None
        info = FileInfo(path)
        info.title = file_row[1]
        info.created = file_row[2] and datetime.fromisoformat(file_row[2])
        cursor.execute('SELECT tag FROM file_tags WHERE file_id = ?', (file_row[0],))
        info.tags = {r[0] for r in cursor.fetchall()}
        cursor.execute('SELECT ref FROM file_refs WHERE referrer_id = ?', (file_row[0],))
        info.refs = {r[0] for r in cursor.fetchall()}
        return info

    def _infos(self):
        # TODO This is super lazy and inefficient.
        #      I should instead get as much info in the initial query as I can,
        #      and avoid doing lookups by path.
        #      It's also super lazy and inefficient that I just rely on the superclass's implementations
        #      of query() etc.
        cursor = self.connection.cursor()
        cursor.execute('SELECT path FROM files WHERE existent = TRUE')
        for (path,) in cursor:
            yield self.info(Path(path))

    def referrers(self, path: Path) -> Set[Path]:
        cursor = self.connection.cursor()
        path = path.resolve()
        cursor.execute('SELECT referrers.path'
                       ' FROM files referrers'
                       '  INNER JOIN file_refs ON referrers.id = file_refs.referrer_id'
                       '  INNER JOIN files referents ON referents.id = file_refs.referent_id'
                       ' WHERE referents.path = ?',
                       (str(path),))
        return {Path(r[0]) for r in cursor.fetchall()}

    def change(self, edits: List[FileEditCmd]):
        try:
            super().change(edits)
        finally:
            # TODO only refresh necessary files
            self.refresh()

    def clear(self):
        self.connection.executescript(SQL_CLEAR)

    def close(self):
        self.connection.close()
