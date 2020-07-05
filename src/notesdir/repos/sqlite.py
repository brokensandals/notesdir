import sqlite3
from notesdir.repos.direct import DirectRepo


CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL,
    existent BOOLEAN,
    stat_ctime INTEGER,
    stat_mtime INTEGER,
    stat_size INTEGER,
    title TEXT,
    creation TEXT
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
    referent_id INTEGER NOT NULL,
    ref TEXT NOT NULL,
    FOREIGN KEY(referrer_id) REFERENCES files(id),
    FOREIGN KEY(referent_id) REFERENCES files(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS file_refs_referrer_id_ref ON file_refs (referrer_id, ref);
CREATE INDEX IF NOT EXISTS file_refs_referrer_id_referent_id ON file_refs (referrer_id, referent_id);
CREATE INDEX IF NOT EXISTS file_refs_referent_id_referrer_id ON file_refs (referent_id, referrer_id);
"""

CLEAR_SQL = """
DELETE FROM files;
DELETE FROM file_tags;
DELETE_FROM file_refs;
"""


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
        self.connection.executescript(CREATE_SCHEMA_SQL)

    def refresh(self):

        pass

    def clear(self):
        self.connection.executescript(CLEAR_SQL)

    def close(self):
        self.connection.close()
