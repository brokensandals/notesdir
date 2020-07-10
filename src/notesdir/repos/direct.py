import base64
import dataclasses
import json
import re
from collections import defaultdict
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import List, Dict, Union, Iterator

from notesdir.accessors.delegating import DelegatingAccessor
from notesdir.models import FileInfo, FileEditCmd, MoveCmd, FileQuery, FileInfoReq
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

    def info(self, path: Union[str, bytes, PathLike], fields: FileInfoReq = FileInfoReq.internal()) -> FileInfo:
        path = Path(path)

        if any(f.search(str(path)) for f in self.noparse) or not path.exists():
            info = FileInfo(path)
        else:
            info = self.accessor_factory(path).info()

        if fields.referrers:
            for other in self.query(fields=FileInfoReq(path=True, refs=True)):
                refs = other.refs_to_path(path)
                if refs:
                    info.referrers[other.path] = refs

        return info

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

    def _paths(self) -> Iterator[Path]:
        for root in self.roots:
            for child in root.resolve().glob('**/*'):
                yield child

    def query(self, query: Union[str, FileQuery] = FileQuery(), fields: FileInfoReq = FileInfoReq.internal())\
            -> Iterator[FileInfo]:
        fields = dataclasses.replace(fields, tags=(fields.tags or query.include_tags or query.exclude_tags))
        query = FileQuery.parse(query)
        for path in self._paths():
            info = self.info(path, fields)
            if not info:
                continue
            if query.include_tags and not query.include_tags.issubset(info.tags):
                continue
            if query.exclude_tags and not query.exclude_tags.isdisjoint(info.tags):
                continue
            yield info

    def tag_counts(self, query: Union[str, FileQuery] = FileQuery()) -> Dict[str, int]:
        query = FileQuery.parse(query)
        result = defaultdict(int)
        for info in self.query(query, FileInfoReq(path=True, tags=True)):
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
