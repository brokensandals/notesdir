from notesdir.repos.sqlite import SqliteRepo


def config(tmpdir):
    roots = [tmpdir.mkdir('notes')]
    cache = tmpdir.join('cache.sqlite3')
    return {'roots': roots, 'cache': cache}


def test_init(tmpdir):
    repo = SqliteRepo(config(tmpdir))
    repo.close()
