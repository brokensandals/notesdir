import base64
import json
import re
from collections import defaultdict
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Set, Optional, List, Dict, Union

from notesdir.accessors.delegating import DelegatingAccessor
from notesdir.models import FileInfo, FileEditCmd, MoveCmd, FileQuery
from notesdir.repos.base import Repo, group_edits, edit_log_json_serializer


class DirectRepo(Repo):
    def __init__(self, config: dict):
        self.config = config
        if 'roots' not in self.config:
            raise ValueError('"roots" must be set in repo config')
        self.roots = {Path(p) for p in self.config['roots']}
        self.noparse = {re.compile(f) for f in self.config.get('noparse', [])}
        self.accessor_factory = DelegatingAccessor
        edit_log_path = self.config.get('edit_log_path', None)
        self.edit_log_path = edit_log_path and Path(edit_log_path)

    def info(self, path: Union[str, bytes, PathLike]) -> Optional[FileInfo]:
        path = Path(path)
        if not path.exists():
            return None
        if any(f.search(str(path)) for f in self.noparse):
            return FileInfo(path)
        return self.accessor_factory(path).info()

    def _paths(self):
        for root in self.roots:
            for child in root.resolve().glob('**/*'):
                yield child

    def _infos(self):
        for path in self._paths():
            info = self.info(path)
            if info:
                yield info

    def referrers(self, path: Union[str, bytes, PathLike]) -> Set[Path]:
        path = Path(path)
        result = set()
        for info in self._infos():
            if len(info.refs_to_path(path)) > 0:
                result.add(info.path)
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

    def query(self, query: Union[str, FileQuery]) -> List[FileInfo]:
        query = FileQuery.parse(query)
        result = []
        for info in self._infos():
            if query.include_tags and not query.include_tags.issubset(info.tags):
                continue
            if query.exclude_tags and not query.exclude_tags.isdisjoint(info.tags):
                continue
            result.append(info)
        return result

    def tag_counts(self, query: Union[str, FileQuery]) -> Dict[str, int]:
        query = FileQuery.parse(query)
        result = defaultdict(int)
        for info in self.query(query):
            for tag in info.tags:
                result[tag] += 1
        return result

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
