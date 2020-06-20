from pathlib import Path
import pytest
from notesdir.accessors.base import BaseAccessor, FileEdit


def test_change_empty():
    assert not BaseAccessor().change([])


def test_change_multiple_paths():
    with pytest.raises(ValueError):
        BaseAccessor().change([FileEdit(Path('a')), FileEdit(Path('b'))])
