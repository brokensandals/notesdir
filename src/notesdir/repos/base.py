import dataclasses
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Set, Union

from notesdir.models import FileInfo, FileEditCmd, MoveCmd, FileQuery


class Repo:
    def info(self, path: Path) -> Optional[FileInfo]:
        raise NotImplementedError()

    def change(self, edits: List[FileEditCmd]):
        raise NotImplementedError()

    def referrers(self, path: Path) -> Set[Path]:
        raise NotImplementedError()

    def query(self, query: Union[str, FileQuery]) -> List[FileInfo]:
        raise NotImplementedError()

    def tag_counts(self, query: Union[str, FileQuery]) -> Dict[str, int]:
        raise NotImplementedError()

    def close(self):
        pass


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