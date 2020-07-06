from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Set, Optional, Dict
from urllib.parse import urlparse, unquote_plus


@dataclass
class FileInfo:
    path: Path
    refs: Set[str] = field(default_factory=set)
    tags: Set[str] = field(default_factory=set)
    title: Optional[str] = None
    created: Optional[datetime] = None

    def path_refs(self) -> Dict[Optional[Path], Set[str]]:
        """Returns subsets of self.refs that refer to local paths.

        Each key of the result is a local path, and the value is the subset of refs
        that refer to it. The same ref will not appear in multiple keys. Refs that
        resolve to the same path will appear under the same key, even if they are
        specified via differing relative paths or paths involving symlinks, or if they
        differ in the fragment or query string of the URL.

        Refs that cannot be parsed as URLs or that do not refer to local paths will
        appear under the key None.
        """
        result = {}
        for ref in self.refs:
            try:
                url = urlparse(ref)
                if (not url.scheme) or (url.scheme == 'file' and url.netloc in ['', 'localhost']):
                    src = Path(unquote_plus(url.path))
                    if not src.is_absolute():
                        src = self.path.joinpath('..', src)
                    src = src.resolve()
                    if src in result:
                        result[src].add(ref)
                    else:
                        result[src] = {ref}
                    continue
            except ValueError:
                pass

            if None in result:
                result[None].add(ref)
            else:
                result[None] = {ref}
        return result

    def refs_to_path(self, dest: Path) -> Set[str]:
        """Returns the value of self.path_refs() for the given path, or an empty set.

        The path is resolved first to account for symlinks or relative paths.
        """
        return self.path_refs().get(dest.resolve(), set())


@dataclass
class FileEditCmd:
    path: Path


@dataclass
class SetTitleCmd(FileEditCmd):
    value: Optional[str]


@dataclass
class SetCreatedCmd(FileEditCmd):
    value: Optional[datetime]


@dataclass
class ReplaceRefCmd(FileEditCmd):
    original: str
    replacement: str


@dataclass
class AddTagCmd(FileEditCmd):
    value: str


@dataclass
class DelTagCmd(FileEditCmd):
    value: str


@dataclass
class MoveCmd(FileEditCmd):
    dest: Path


@dataclass
class FileQuery:
    include_tags: Set[str] = field(default_factory=set)
    exclude_tags: Set[str] = field(default_factory=set)

    @classmethod
    def parse(cls, strquery: str) -> FileQuery:
        query = cls()
        for term in strquery.split():
            term = term.strip()
            lower = term.lower()
            if lower.startswith('tag:'):
                query.include_tags.update(unquote_plus(t) for t in lower[4:].split(','))
            elif lower.startswith('-tag:'):
                query.exclude_tags.update(unquote_plus(t) for t in lower[5:].split(','))
        return query
