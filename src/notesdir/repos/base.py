import dataclasses
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Iterator

from notesdir.models import FileInfo, FileEditCmd, MoveCmd, FileQuery, SetTitleCmd, SetCreatedCmd, AddTagCmd,\
    DelTagCmd, ReplaceRefCmd, FileInfoReq, FileInfoReqIsh, FileQueryIsh, PathIsh


class Repo:
    def info(self, path: PathIsh, fields: FileInfoReqIsh = FileInfoReq.internal()) -> FileInfo:
        raise NotImplementedError()

    def change(self, edits: List[FileEditCmd]):
        raise NotImplementedError()

    def query(self, query: FileQueryIsh = FileQuery(), fields: FileInfoReqIsh = FileInfoReq.internal())\
            -> Iterator[FileInfo]:
        raise NotImplementedError()

    def tag_counts(self, query: FileQueryIsh = FileQuery()) -> Dict[str, int]:
        raise NotImplementedError()

    def close(self):
        pass

    def add_tag(self, path: PathIsh, tag: str):
        """Convenience method equivalent to calling change with one AddTagCmd."""
        self.change([AddTagCmd(Path(path), tag)])

    def del_tag(self, path: PathIsh, tag: str):
        """Convenience method equivalent to calling change with one DelTagCmd."""
        self.change([DelTagCmd(Path(path), tag)])

    def set_created(self, path: PathIsh, created: datetime):
        """Convenience method equivalent to calling change with one SetCreatedCmd."""
        self.change([SetCreatedCmd(Path(path), created)])

    def set_title(self, path: PathIsh, title: str):
        """Convenience method equivalent to calling change with one SetTitleCmd."""
        self.change([SetTitleCmd(Path(path), title)])

    def replace_ref(self, path: PathIsh, original: str, replacement: str):
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