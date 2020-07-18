"""Provides the :class:`DirectRepo` class."""

import dataclasses
from operator import attrgetter
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Iterator, Set

from notesdir.accessors.delegating import DelegatingAccessor
from notesdir.conf import DirectRepoConf
from notesdir.models import FileInfo, FileEditCmd, MoveCmd, FileQuery, FileInfoReq, PathIsh, FileInfoReqIsh,\
    FileQueryIsh
from notesdir.repos.base import Repo, _group_edits


class DirectRepo(Repo):
    """Accesses notes directly on the filesystem without any caching.

    This performs fine if you only have a few dozen notes, but beyond that you want a caching implementation
    (see :class:`notesdir.repos.sqlite.SqliteRepo`), because looking up backlinks for a file requires reading all
    the other files, which gets very slow.

    .. attribute:: conf
       :type: DirectRepoConf
    """
    def __init__(self, conf: DirectRepoConf):
        self.conf = conf
        if not conf.root_paths:
            raise ValueError('`root_paths` must be non-empty in RepoConf.')
        self.accessor_factory = DelegatingAccessor

    def _should_skip_parse(self, path: Path) -> bool:
        return any(self.conf.skip_parse(p) for p in reversed(path.parents)) or self.conf.skip_parse(path)

    def info(self, path: PathIsh, fields: FileInfoReqIsh = FileInfoReq.internal()) -> FileInfo:
        path = Path(path).resolve()
        fields = FileInfoReq.parse(fields)

        if self._should_skip_parse(path) or not path.exists():
            info = FileInfo(path)
        else:
            info = self.accessor_factory(path).info()

        if fields.backlinks:
            for other in self.query(fields=FileInfoReq(path=True, links=True)):
                info.backlinks.extend(link for link in other.links if link.referent() == path)
            info.backlinks.sort(key=attrgetter('referrer', 'href'))

        return info

    def change(self, edits: List[FileEditCmd]):
        for group in _group_edits(edits):
            if isinstance(group[0], MoveCmd):
                for edit in group:
                    edit.path.rename(edit.dest)
            else:
                acc = self.accessor_factory(group[0].path)
                for edit in group:
                    acc.edit(edit)
                acc.save()

    def invalidate(self, only: Set[PathIsh] = None):
        """No-op."""
        pass

    def _paths(self) -> Iterator[Path]:
        for root in self.conf.root_paths:
            if root.is_dir():
                yield from self._paths_in(root)
            elif root.is_file():
                yield root

    def _paths_in(self, path: Path) -> Iterator[Path]:
        for child in path.iterdir():
            if self.conf.ignore(child):
                continue
            if child.is_dir():
                yield from self._paths_in(child)
            else:
                yield child

    def query(self, query: FileQueryIsh = FileQuery(), fields: FileInfoReqIsh = FileInfoReq.internal())\
            -> Iterator[FileInfo]:
        fields = dataclasses.replace(FileInfoReq.parse(fields),
                                     tags=(fields.tags or query.include_tags or query.exclude_tags))
        query = FileQuery.parse(query)
        yield from query.apply_filtering(self.info(path, fields) for path in self._paths())

    def tag_counts(self, query: FileQueryIsh = FileQuery()) -> Dict[str, int]:
        query = FileQuery.parse(query)
        result = defaultdict(int)
        for info in self.query(query, FileInfoReq(path=True, tags=True)):
            for tag in info.tags:
                result[tag] += 1
        return result
