import os.path
import pytest
from notesdir.api import Error, Notesdir


def test_for_user_no_file(fs):
    with pytest.raises(Error, match=r'No config file found at .*\.notesdir\.toml'):
        Notesdir.for_user()


def test_for_user(fs):
    fs.create_file(os.path.expanduser('~/.notesdir.toml'), contents='repo.roots = ["/foo"]')
    nd = Notesdir.for_user()
    assert nd.config == {'repo': {'roots': ['/foo']}}
