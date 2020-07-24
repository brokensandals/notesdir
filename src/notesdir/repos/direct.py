"""Provides the :class:`DirectRepo` class."""

import dataclasses
from operator import attrgetter
from collections import defaultdict, namedtuple
import os
import os.path
from typing import List, Dict, Iterator, Set

from notesdir.accessors.delegating import DelegatingAccessor
from notesdir.conf import DirectRepoConf
from notesdir.models import FileInfo, FileEditCmd, MoveCmd, FileQuery, FileInfoReq, FileInfoReqIsh,\
    FileQueryIsh, CreateCmd
from notesdir.repos.base import Repo, _group_edits


PathEntry = namedtuple('PathEntry', ['dir_entry', 'skip_parse'])


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

    def _should_skip_parse(self, path: str) -> bool:
        parent, basename = os.path.split(path)
        prev = path
        while not parent == prev:
            if self.conf.ignore(parent, basename) or self.conf.skip_parse(parent, basename):
                return True
            prev = parent
            parent, basename = os.path.split(parent)
        return False

    def info(self, path: str, fields: FileInfoReqIsh = FileInfoReq.internal(),
             path_resolved=False, skip_parse=None) -> FileInfo:
        if not path_resolved:
            path = os.path.abspath(path)
        if skip_parse is None:
            skip_parse = self._should_skip_parse(path)
        fields = FileInfoReq.parse(fields)

        if skip_parse or not os.path.exists(path):
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
            if self.conf.preview_mode:
                for edit in group:
                    print(edit)
                continue

            if isinstance(group[0], MoveCmd):
                for edit in group:
                    if edit.create_parents:
                        parent = os.path.split(edit.dest)[0]
                        os.makedirs(parent, exist_ok=True)
                    os.rename(edit.path, edit.dest)
                    if edit.delete_empty_parents:
                        prev = edit.path
                        parent = os.path.split(prev)[0]
                        while parent and not parent == prev:
                            if os.path.exists(parent):
                                if sum(1 for _ in os.listdir(parent)):
                                    break
                                os.rmdir(parent)
                            prev = parent
                            parent = os.path.split(parent)[0]
            elif isinstance(group[0], CreateCmd):
                for edit in group:
                    with open(edit.path, 'w') as file:
                        file.write(edit.contents)
            else:
                acc = self.accessor_factory(group[0].path)
                for edit in group:
                    acc.edit(edit)
                acc.save()

    def invalidate(self, only: Set[str] = None):
        """No-op."""
        pass

    def _paths(self) -> Iterator[PathEntry]:
        for root in self.conf.root_paths:
            if os.path.isdir(root):
                parent, basename = os.path.split(root)
                skip_parse = self.conf.skip_parse(parent, basename)
                yield from self._paths_in(root, skip_parse=skip_parse)

    def _paths_in(self, dirpath: str, skip_parse: bool) -> Iterator[PathEntry]:
        for entry in os.scandir(dirpath):
            if entry.is_symlink():
                continue
            if self.conf.ignore(dirpath, entry.name):
                continue
            entry_skip_parse = skip_parse or self.conf.skip_parse(dirpath, entry.name)
            if entry.is_dir():
                yield from self._paths_in(entry.path, skip_parse=entry_skip_parse)
            else:
                yield PathEntry(entry, skip_parse=entry_skip_parse)

    def query(self, query: FileQueryIsh = FileQuery(), fields: FileInfoReqIsh = FileInfoReq.internal())\
            -> Iterator[FileInfo]:
        fields = dataclasses.replace(FileInfoReq.parse(fields),
                                     tags=(fields.tags or query.include_tags or query.exclude_tags))
        query = FileQuery.parse(query)
        filtered = query.apply_filtering(
            self.info(e.dir_entry.path, fields, path_resolved=True, skip_parse=e.skip_parse)
            for e in self._paths())
        yield from query.apply_sorting(filtered)

    def tag_counts(self, query: FileQueryIsh = FileQuery()) -> Dict[str, int]:
        query = FileQuery.parse(query)
        result = defaultdict(int)
        for info in self.query(query, FileInfoReq(path=True, tags=True)):
            for tag in info.tags:
                result[tag] += 1
        return result
