import dataclasses
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Dict, Optional, List, Set, Union

from notesdir.models import FileInfo, FileEditCmd, MoveCmd, FileQuery, SetTitleCmd, SetCreatedCmd, AddTagCmd,\
    DelTagCmd, ReplaceRefCmd


class Repo:
    def info(self, path: Union[str, bytes, PathLike]) -> Optional[FileInfo]:
        raise NotImplementedError()

    def change(self, edits: List[FileEditCmd]):
        raise NotImplementedError()

    def referrers(self, path: Union[str, bytes, PathLike]) -> Set[Path]:
        raise NotImplementedError()

    def query(self, query: Union[str, FileQuery]) -> List[FileInfo]:
        raise NotImplementedError()

    def tag_counts(self, query: Union[str, FileQuery]) -> Dict[str, int]:
        raise NotImplementedError()

    def close(self):
        pass

    def add_tag(self, path: Union[str, bytes, PathLike], tag: str):
        """Convenience method equivalent to calling change with one AddTagCmd."""
        self.change([AddTagCmd(Path(path), tag)])

    def del_tag(self, path: Union[str, bytes, PathLike], tag: str):
        """Convenience method equivalent to calling change with one DelTagCmd."""
        self.change([DelTagCmd(Path(path), tag)])

    def set_created(self, path: Union[str, bytes, PathLike], created: datetime):
        """Convenience method equivalent to calling change with one SetCreatedCmd."""
        self.change([SetCreatedCmd(Path(path), created)])

    def set_title(self, path: Union[str, bytes, PathLike], title: str):
        """Convenience method equivalent to calling change with one SetTitleCmd."""
        self.change([SetTitleCmd(Path(path), title)])

    def replace_ref(self, path: Union[str, bytes, PathLike], original: str, replacement: str):
        """Convenience method equivalent to calling change with one ReplaceRefCmd."""
        self.change([ReplaceRefCmd(Path(path), original, replacement)])


def group_edits(edits: List[FileEditCmd]) -> List[List[FileEditCmd]]:
    group = None
    result = []
    for edit in edits:
        if group and edit.path == group[0].path and not isinstance(edit, MoveCmd):
            group.append(edit)
        else:
            group = [edit]
            result.append(group)
    return result


def edit_log_json_serializer(val):
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, FileEditCmd):
        d = dataclasses.asdict(val)
        del d['path']
        d['class'] = type(val).__name__
        return d
    return str(val)