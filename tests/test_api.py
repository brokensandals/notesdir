import os.path
import pytest
from notesdir.api import Error, Notesdir


def test_user_default_no_file(fs):
    with pytest.raises(Error, match=r'No config file found at .*\.notesdir\.toml'):
        Notesdir.user_default()


def test_user_default(fs):
    fs.create_file(os.path.expanduser('~/.notesdir.toml'), contents='paths = ["/foo/**/*"]')
    nd = Notesdir.user_default()
    assert nd.config == {'paths': ['/foo/**/*']}
