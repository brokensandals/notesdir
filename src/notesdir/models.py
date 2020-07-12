from __future__ import annotations
from dataclasses import dataclass, field, replace
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Set, Optional, Union, Iterable, List
from urllib.parse import urlparse, unquote_plus


PathIsh = Union[str, bytes, PathLike]


@dataclass
class LinkInfo:
    referrer: Path
    href: str

    def referent(self):
        try:
            url = urlparse(self.href)
            if (not url.scheme) or (url.scheme == 'file' and url.netloc in ['', 'localhost']):
                referent = Path(unquote_plus(url.path))
                if not referent.is_absolute():
                    referent = self.referrer.joinpath('..', referent)
                return referent.resolve()
        except ValueError:
            # not a valid URL
            return None

    def as_json(self) -> dict:
        """Returns a dict representing the instance, suitable for serializing as json."""
        referent = self.referent()
        return {
            'referrer': str(self.referrer),
            'href': self.href,
            'referent': str(referent) if referent else None
        }


@dataclass
class FileInfo:
    path: Path
    links: List[LinkInfo] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    title: Optional[str] = None
    created: Optional[datetime] = None
    backlinks: List[LinkInfo] = field(default_factory=list)

    def as_json(self) -> dict:
        """Returns a dict representing the instance, suitable for serializing as json."""
        return {
            'path': str(self.path),
            'title': self.title,
            'created': self.created.isoformat() if self.created else None,
            'tags': sorted(self.tags),
            'links': [link.as_json() for link in self.links],
            'backlinks': [link.as_json() for link in self.backlinks]
        }


@dataclass
class FileInfoReq:
    @classmethod
    def parse(cls, val: FileInfoReqIsh) -> FileInfoReq:
        if isinstance(val, FileInfoReq):
            return val
        if isinstance(val, str):
            return cls.parse(s for s in val.split(',') if s.strip())
        return cls(**{k: True for k in val})

    @classmethod
    def internal(cls) -> FileInfoReq:
        return cls(path=True, links=True, tags=True, title=True, created=True)

    @classmethod
    def full(cls) -> FileInfoReq:
        return replace(cls.internal(), backlinks=True)

    path: bool = False
    links: bool = False
    tags: bool = False
    title: bool = False
    created: bool = False
    backlinks: bool = False


FileInfoReqIsh = Union[str, Iterable[str], FileInfoReq]


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
class ReplaceHrefCmd(FileEditCmd):
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
    def parse(cls, strquery: Union[str, FileQuery]) -> FileQuery:
        if isinstance(strquery, FileQuery):
            return strquery
        query = cls()
        for term in strquery.split():
            term = term.strip()
            lower = term.lower()
            if lower.startswith('tag:'):
                query.include_tags.update(unquote_plus(t) for t in lower[4:].split(','))
            elif lower.startswith('-tag:'):
                query.exclude_tags.update(unquote_plus(t) for t in lower[5:].split(','))
        return query


FileQueryIsh = Union[str, FileQuery]


@dataclass
class TemplateDirectives:
    dest: Optional[Path] = None
    create_resources_dir: bool = False
