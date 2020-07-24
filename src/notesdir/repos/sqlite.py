"""Provides the :class:`SqliteRepo` class."""

from collections import namedtuple
from datetime import datetime
import dataclasses
from operator import attrgetter
import os.path
import sqlite3
from typing import List, Iterator, Set
from notesdir.conf import SqliteRepoConf
from notesdir.models import FileInfo, FileEditCmd, FileInfoReq, FileQuery, FileQueryIsh, FileInfoReqIsh,\
    LinkInfo
from notesdir.repos.direct import DirectRepo


_SQL_CREATE_SCHEMA = """
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

CREATE TABLE IF NOT EXISTS file_links (
    id INTEGER PRIMARY KEY,
    referrer_id INTEGER NOT NULL,
    referent_id INTEGER,
    href TEXT NOT NULL,
    FOREIGN KEY(referrer_id) REFERENCES files(id),
    FOREIGN KEY(referent_id) REFERENCES files(id)
);

CREATE INDEX IF NOT EXISTS file_links_referrer_id_href ON file_links (referrer_id, href);
CREATE INDEX IF NOT EXISTS file_links_referrer_id_referent_id ON file_links (referrer_id, referent_id);
CREATE INDEX IF NOT EXISTS file_links_referent_id_referrer_id ON file_links (referent_id, referrer_id);
"""

_SQL_CLEAR = """
DELETE FROM files;
DELETE FROM file_tags;
DELETE_FROM file_refs;
"""


_SQL_ALL_FOR_REFRESH = 'SELECT id, path, stat_ctime, stat_mtime, stat_size FROM files'
_SqlAllForRefreshRow = namedtuple('SqlAllForRefreshRow', ['id', 'path', 'stat_ctime', 'stat_mtime', 'stat_size'])

_SQL_INSERT_FILE = ('INSERT INTO files (path, existent, stat_ctime, stat_mtime, stat_size, title, created)'
                    ' VALUES (?, ?, ?, ?, ?, ?, ?)')
_SqlInsertFileRow = namedtuple('SqlInsertFileRow', ['path', 'existent', 'stat_ctime', 'stat_mtime', 'stat_size',
                                                    'title', 'created'])

_SQL_UPDATE_FILE = ('UPDATE files SET existent = ?, stat_ctime = ?, stat_mtime = ?, stat_size = ?,'
                    ' title = ?, created = ?'
                    ' WHERE id = ?')
_SqlUpdateFileRow = namedtuple('SqlUpdateFileRow', ['existent', 'stat_ctime', 'stat_mtime', 'stat_size',
                                                    'title', 'created', 'id'])


class SqliteRepo(DirectRepo):
    """Keeps a cache of note metadata/links in a SQLite database.

    The database file is only a cache: you can safely delete it and it will be rebuilt the next time you create a
    :class:`SqliteRepo` instance. Corrupting or deleting the file during operation may cause erratic behavior, though.

    The modification timestamp and other filesystem metadata for each file in your note directories
    are stored in the database. Each time a :class:`SqliteRepo` instance is created or :meth:`change` is
    called, the files are scanned to see if this metadata has changed for any of them; if so, those files are parsed
    again and the cache is updated.

    Remember to call :meth:`close` when done with the instance, or use the instance as a context manager.

    .. attribute:: conf
       :type: notesdir.conf.SqliteRepoConf
    """
    def __init__(self, conf: SqliteRepoConf):
        super().__init__(conf)
        if not conf.cache_path:
            raise ValueError('`cache_path` must be set in SqliteRepoConf.')
        self.connection = None
        self._connect()
        self.invalidate()

    def _connect(self):
        self.connection = sqlite3.connect(self.conf.cache_path)
        self.connection.executescript(_SQL_CREATE_SCHEMA)

    def _refresh(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(_SQL_ALL_FOR_REFRESH)
        prior_rows = (_SqlAllForRefreshRow(*r) for r in cursor.fetchall())
        prior_rows_by_path = {r.path: r for r in prior_rows}
        found_paths = set()

        ids_by_path = {}
        links_to_add = []

        for path_entry in self._paths():
            dir_entry = path_entry.dir_entry
            pathstr = dir_entry.path
            found_paths.add(pathstr)
            row = prior_rows_by_path.get(pathstr)
            if row and path_entry.skip_parse:
                # TODO currently we do not clear out old data for files that were previously parsable but are now
                #      marked skip_parse
                continue
            stat = dir_entry.stat()
            if (row and row.stat_ctime == stat.st_ctime
                    and row.stat_mtime == stat.st_mtime
                    and row.stat_size == stat.st_size):
                continue
            info = super().info(pathstr, path_resolved=True, skip_parse=path_entry.skip_parse)
            if row:
                file_id = row.id
                cursor.execute('DELETE FROM file_tags WHERE file_id = ?', (file_id,))
                cursor.execute('DELETE FROM file_links WHERE referrer_id = ?', (file_id,))
                updrow = _SqlUpdateFileRow(id=file_id,
                                           existent=True,
                                           stat_ctime=stat.st_ctime,
                                           stat_mtime=stat.st_mtime,
                                           stat_size=stat.st_size,
                                           title=info.title,
                                           created=info.created)
                cursor.execute(_SQL_UPDATE_FILE, updrow)
            else:
                newrow = _SqlInsertFileRow(path=pathstr,
                                           existent=True,
                                           stat_ctime=stat.st_ctime,
                                           stat_mtime=stat.st_mtime,
                                           stat_size=stat.st_size,
                                           title=info.title,
                                           created=info.created)
                cursor.execute(_SQL_INSERT_FILE, newrow)
                file_id = cursor.lastrowid
            cursor.executemany('INSERT INTO file_tags (file_id, tag) VALUES (?, ?)',
                               ((file_id, t) for t in info.tags))
            ids_by_path[pathstr] = file_id
            links_to_add.extend((file_id, link) for link in info.links)

        for referrer_id, link in links_to_add:
            referent_id = None
            referent = link.referent()
            if referent:
                referent_str = str(referent)
                found_paths.add(referent_str)
                referent_id = ids_by_path.get(referent_str)
                if not referent_id:
                    prior_row = prior_rows_by_path.get(referent_str)
                    if prior_row:
                        referent_id = prior_row.id
                if not referent_id:
                    cursor.execute('INSERT INTO files (path, existent) VALUES (?, FALSE)', (referent_str,))
                    referent_id = cursor.lastrowid
                    ids_by_path[referent_str] = referent_id
            cursor.execute('INSERT INTO file_links (referrer_id, referent_id, href)'
                           ' VALUES (?, ?, ?)',
                           (referrer_id, referent_id, link.href))

        ids_to_delete = [prior_rows_by_path[p].id for p in set(prior_rows_by_path.keys()).difference(found_paths)]
        for id_to_delete in ids_to_delete:
            cursor.execute('SELECT COUNT(*) FROM file_links WHERE referent_id = ?', (id_to_delete,))
            if cursor.fetchone()[0] == 0:
                cursor.execute('DELETE FROM files WHERE id = ?', (id_to_delete,))
            else:
                updrow = _SqlUpdateFileRow(id=id_to_delete,
                                           existent=False,
                                           stat_ctime=None,
                                           stat_mtime=None,
                                           stat_size=None,
                                           title=None,
                                           created=None)
                cursor.execute(_SQL_UPDATE_FILE, updrow)
            cursor.execute('DELETE FROM file_tags WHERE file_id = ?', (id_to_delete,))
            cursor.execute('DELETE FROM file_links WHERE referrer_id = ?', (id_to_delete,))

        self.connection.commit()
        self._needs_refresh = False

    def _refresh_if_needed(self) -> None:
        if self._needs_refresh:
            self._refresh()

    def invalidate(self, only: Set[str] = None) -> None:
        # TODO support `only`
        self._needs_refresh = True

    def info(self, path: str, fields: FileInfoReqIsh = FileInfoReq.internal(), path_resolved=False) -> FileInfo:
        self._refresh_if_needed()
        if not path_resolved:
            path = os.path.abspath(path)
        fields = FileInfoReq.parse(fields)
        cursor = self.connection.cursor()
        cursor.execute('SELECT id, title, created FROM files WHERE path = ?', (path,))
        file_row = cursor.fetchone()
        info = FileInfo(path)
        if file_row:
            file_id = file_row[0]
            info.title = file_row[1]
            info.created = file_row[2] and datetime.fromisoformat(file_row[2])
            if fields.tags:
                cursor.execute('SELECT tag FROM file_tags WHERE file_id = ?', (file_id,))
                info.tags = {r[0] for r in cursor}
            if fields.links:
                cursor.execute('SELECT href FROM file_links WHERE referrer_id = ?', (file_id,))
                info.links = [LinkInfo(path, href) for href in sorted(r[0] for r in cursor)]
            if fields.backlinks:
                cursor.execute('SELECT referrers.path, file_links.href'
                               ' FROM files referrers'
                               '  INNER JOIN file_links ON referrers.id = file_links.referrer_id'
                               ' WHERE file_links.referent_id = ?',
                               (file_id,))
                info.backlinks = [LinkInfo(referrer, href) for referrer, href in cursor]
                info.backlinks.sort(key=attrgetter('referrer', 'href'))
        return info

    def query(self, query: FileQueryIsh = FileQuery(), fields: FileInfoReqIsh = FileInfoReq.internal())\
            -> Iterator[FileInfo]:
        self._refresh_if_needed()
        query = FileQuery.parse(query)
        cursor = self.connection.cursor()
        cursor.execute('SELECT path FROM files WHERE existent = TRUE')
        # TODO: Obviously, this is super lazy and inefficient. We should do as much filtering and data loading in
        #       the query as we reasonably can.
        fields = dataclasses.replace(FileInfoReq.parse(fields),
                                     tags=(fields.tags or query.include_tags or query.exclude_tags))
        filtered = query.apply_filtering(self.info(path, fields, path_resolved=True) for (path,) in cursor)
        yield from query.apply_sorting(filtered)

    def change(self, edits: List[FileEditCmd]):
        try:
            super().change(edits)
        finally:
            # TODO only invalidate necessary files
            if not self.conf.preview_mode:
                self.invalidate()

    def clear(self):
        self.connection.executescript(_SQL_CLEAR)
        self.invalidate()

    def close(self):
        self.connection.close()
        self.connection = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
