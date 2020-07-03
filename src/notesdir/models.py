from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Set, Optional, Dict
from urllib.parse import urlparse, unquote_plus


@dataclass
class FileInfo:
    path: Path
    refs: Set[str] = field(default_factory=set)
    managed_tags: Set[str] = field(default_factory=set)
    unmanaged_tags: Set[str] = field(default_factory=set)
    title: Optional[str] = None
    created: Optional[datetime] = None

    def all_tags(self) -> Set[str]:
        return self.managed_tags.union(self.unmanaged_tags)

    def path_refs(self) -> Dict[Path, Set[str]]:
        """Returns subsets of self.refs that refer to local paths.

        Each key of the result is a local path, and the value is the subset of refs
        that refer to it. The same ref will not appear in multiple keys. Refs that
        resolve to the same path will appear under the same key, even if they are
        specified via differing relative paths or paths involving symlinks, or if they
        differ in the fragment or query string of the URL.

        Refs that cannot be parsed as URLs or that do not refer to local paths will
        not appear in the result.
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
                        result[src] = set([ref])
            except ValueError:
                pass
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
class MoveCmd(FileEditCmd):
    dest: Path
