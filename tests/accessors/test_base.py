import pytest
from notesdir.accessors.base import Accessor
from notesdir.models import FileEditCmd


def test_edit_wrong_path():
    with pytest.raises(ValueError):
        Accessor('foo').edit(FileEditCmd('bar'))
