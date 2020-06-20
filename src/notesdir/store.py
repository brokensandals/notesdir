import os
from os.path import relpath
from pathlib import Path
from typing import Dict, Optional
from notesdir.accessors.base import BaseAccessor, FileInfo


def ref_path(src: Path, dest: Path) -> Path:
    """Returns the path to use for a reference from file src to file dest.

    This is a relative path to dest from the directory containing src.
    For example, for src `/foo/bar/baz.md` and dest `/foo/meh/blah.png`,
    returns `../meh/blah.png`.

    src and dest are resolved before calculating the relative path.
    """
    result = relpath(dest.resolve(), src.resolve())
    if result.startswith(f'..{os.sep}'):
        result = result[3:]
    if result == '':
        result = '.'
    return Path(result)


class FSStore:
    def __init__(self, root: Path, accessor: BaseAccessor):
        self.root = root
        self.accessor = accessor

    def info(self, path: Path) -> Optional[FileInfo]:
        return self.accessor.parse(path)

    def referrers(self, path: Path) -> Dict[Path, Path]:
        result = set()
        for child_path in self.root.glob('**/*'):
            pass
        pass
