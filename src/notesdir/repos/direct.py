import base64
import json
import re
from datetime import datetime
from glob import iglob
from pathlib import Path
from typing import Set, Callable, Optional, List

from notesdir.accessors.base import Accessor
from notesdir.models import FileInfo, FileEditCmd, MoveCmd
from notesdir.repos.base import Repo, group_edits, edit_log_json_serializer


class DirectRepo(Repo):
    def __init__(self, paths: Set[str], accessor_factory: Callable[[Path], Accessor],
                 *, filters: Set[re.Pattern] = None, edit_log_path: Path = None):
        self.paths = paths
        self.filters = filters or set()
        self.accessor_factory = accessor_factory
        self.edit_log_path = edit_log_path

    def info(self, path: Path) -> Optional[FileInfo]:
        return self.accessor_factory(path).info()

    def _paths(self):
        for path in self.paths:
            for child in iglob(path, recursive=True):
                if not any(f.search(child) for f in self.filters):
                    yield Path(child)

    def referrers(self, path: Path) -> Set[Path]:
        result = set()
        for child_path in self._paths():
            if not child_path.is_file():
                # This is a little bit of a hack to make the tests simpler -
                # when using DelegatingAccessor it's fine to call .info on a directory,
                # as you'll just get an empty FileInfo back, but some of the tests use
                # other accessors directly, where calling .info on a directory would
                # cause an error.
                continue
            info = self.info(child_path)
            if info and len(info.refs_to_path(path)) > 0:
                result.add(child_path)
        return result

    def change(self, edits: List[FileEditCmd]):
        for group in group_edits(edits):
            self._log_edits(group)
            if isinstance(group[0], MoveCmd):
                for edit in group:
                    edit.path.rename(edit.dest)
            else:
                acc = self.accessor_factory(group[0].path)
                for edit in group:
                    acc.edit(edit)
                acc.save()

    def _log_edits(self, edit_group: List[FileEditCmd]):
        if self.edit_log_path:
            path = edit_group[0].path
            entry = {
                'datetime': datetime.now(),
                'path': path,
                'edits': edit_group,
            }
            if path.is_file():
                try:
                    entry['prior_text'] = path.read_text()
                except:
                    entry['prior_base64'] = base64.b64encode(path.read_bytes()).decode('utf-8')
            with self.edit_log_path.open('a+') as file:
                print(json.dumps(entry, default=edit_log_json_serializer), file=file)