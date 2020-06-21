import os
from os.path import relpath
from pathlib import Path
from typing import Dict, List, Optional, Set
from notesdir.accessors.base import BaseAccessor, FileEdit, FileInfo


def group_edits(edits: List[FileEdit]) -> List[List[FileEdit]]:
    group = None
    result = []
    for edit in edits:
        if group and edit.path == group[0].path and not edit.ACTION == 'move':
            group.append(edit)
        else:
            group = [edit]
            result.append(group)
    return result


def ref_path(src: Path, dest: Path) -> Path:
    """Returns the path to use for a reference from file src to file dest.

    This is a relative path to dest from the directory containing src.

    For example, for src `/foo/bar/baz.md` and dest `/foo/meh/blah.png`,
    returns `../meh/blah.png`.

    src and dest are resolved before calculating the relative path.
    """
    src = src.resolve()
    dest = dest.resolve()
    result = relpath(dest, src)
    if result == '.':
        result = dest.name
    elif result == '..':
        result = '.'
    elif result.startswith(f'..{os.sep}'):
        result = result[3:]
        if result == '':
            result = '.'
    return Path(result)


class BaseStore:
    def info(self, path: Path) -> Optional[FileInfo]:
        raise NotImplementedError()

    def change(self, edits: List[FileEdit]):
        raise NotImplementedError()

    def referrers(self, path: Path) -> Set[Path]:
        raise NotImplementedError()


class FSStore(BaseStore):
    def __init__(self, root: Path, accessor: BaseAccessor):
        self.root = root
        self.accessor = accessor

    def info(self, path: Path) -> Optional[FileInfo]:
        return self.accessor.parse(path)

    def referrers(self, path: Path) -> Set[Path]:
        result = set()
        for child_path in self.root.glob('**/*'):
            info = self.info(child_path)
            if info and len(info.refs_to_path(path)) > 0:
                result.add(child_path)
        return result

    def change(self, edits: List[FileEdit]):
        for group in group_edits(edits):
            if group[0].ACTION == 'move':
                for edit in group:
                    edit.path.rename(edit.dest)
            else:
                self.accessor.change(group)
