"""Defines classes for representing note details, queries, and update requests.

The most important classes are :class:`FileInfo` , :class:`FileEditCmd` , and :class:`FileQuery`
"""

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
    """Represents a link from a file to some resource.

    Not all links target local files, but those are the ones most important to notesdir. The :meth:`referent` method
    can be used to determine what local file, if any, the href targets.
    """

    referrer: Path
    """The file that contains the link. This should be a resolved, absolute path."""

    href: str
    """The linked address.

    Normally this is some sort of URI - it's the address portion of a Markdown link,
    or the ``href`` or ``src`` attribute of an HTML tag, etc.
    """

    def referent(self) -> Optional[Path]:
        """Returns the resolved, absolute local path that this link refers to.

        The path will be returned even if no file or folder actually exists at that location.

        None will be returned if the href cannot be parsed or appears to be a non-file URI.
        """
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
    """Container for the details Notesdir can parse or calculate about a file or folder.

    A FileInfo instance does not imply that its path actually exists - instances may be created for
    nonexistent paths that have just the :attr:`path` and :attr:`backlinks` attributes filled in.

    When you retrieve instances of this from methods like :meth:`notesdir.repos.base.Repo.info`, which fields
    are populated depends on which fields you request via the :class:`FileInfoReq`, as well as what fields
    are supported for the file type and what data is populated in the particular file.
    """

    path: Path
    """The resolved, absolute path for which this information applies."""

    links: List[LinkInfo] = field(default_factory=list)
    """Links from this file to other files or resources."""

    tags: Set[str] = field(default_factory=set)
    """Tags for the file (e.g. "journal" or "project-idea")."""

    title: Optional[str] = None
    """The title of the document, if any."""

    created: Optional[datetime] = None
    """The creation date of the document, according to metadata within the document, if any.

    This will *not* automatically be populated with timestamps from the filesystem, but
    see :meth:`guess_created`.
    """

    backlinks: List[LinkInfo] = field(default_factory=list)
    """Links from other files to this file."""

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

    def guess_created(self) -> Optional[datetime]:
        """Returns the first available of: :attr:`created`, or the file's birthtime, or the file's ctime.

        Returns None for paths that don't exist.
        """
        if self.created:
            return self.created
        if not (self.path and self.path.exists()):
            return None
        stat = self.path.stat()
        try:
            return datetime.utcfromtimestamp(stat.st_birthtime)
        except AttributeError:
            return datetime.utcfromtimestamp(stat.st_ctime)


@dataclass
class FileInfoReq:
    """Allows you to specify which attributes you want when loading or querying for files.

    For each attribute of :class:`FileInfo`, there is a corresponding boolean attribute here, which you
    should set to True to indicate that you want that attribute.

    Some methods that take a FileInfoReq parameter also accept strings or lists of strings as a convenience,
    which they will pass to :meth:`parse`.
    """

    path: bool = False
    links: bool = False
    tags: bool = False
    title: bool = False
    created: bool = False
    backlinks: bool = False

    @classmethod
    def parse(cls, val: FileInfoReqIsh) -> FileInfoReq:
        """Converts the parameter to a FileInfoReq, if it isn't one already.

        You can pass a comma-separated string like ``"path,backlinks"`` or a list of strings like
        ``['path', 'backlinks']``. Each listed field will be set to True in the resulting FileInfoReq.
        """
        if isinstance(val, FileInfoReq):
            return val
        if isinstance(val, str):
            return cls.parse(s for s in val.split(',') if s.strip())
        return cls(**{k: True for k in val})

    @classmethod
    def internal(cls) -> FileInfoReq:
        """Returns an instance that requests everything which can be determined by looking at a file in isolation.

        Currently this means everything except backlinks."""
        return cls(path=True, links=True, tags=True, title=True, created=True)

    @classmethod
    def full(cls) -> FileInfoReq:
        """Returns an instance that requests everything."""
        return replace(cls.internal(), backlinks=True)


FileInfoReqIsh = Union[str, Iterable[str], FileInfoReq]


@dataclass
class FileEditCmd:
    """Base class for requests to make changes to a file."""

    path: Path
    """Path to the file or folder that should be changed."""


@dataclass
class SetTitleCmd(FileEditCmd):
    """Represents a request to change a document's title."""

    value: Optional[str]
    """The new title, or None to delete the title."""


@dataclass
class SetCreatedCmd(FileEditCmd):
    """Represents a request to change the creation date stored in a document's metadata (not filesystem metadata)."""

    value: Optional[datetime]
    """The new creation date, or None to delete it from the metadata."""


@dataclass
class ReplaceHrefCmd(FileEditCmd):
    """Represents a request to replace link addresses in a document.

    All occurrences will be replaced, but only if they are exact matches.
    """

    original: str
    """The value to be replaced, generally copied from a :class:`LinkInfo` :attr:`href`"""

    replacement: str
    """The new link address."""


@dataclass
class AddTagCmd(FileEditCmd):
    """Represents a request to add a tag to a document.

    If the document already contains the tag, this request should be treated as a no-op.
    """

    value: str
    """The tag to add."""


@dataclass
class DelTagCmd(FileEditCmd):
    """Represents a request to remove a tag from a document.

    If the document does not contain the tag, this request should be treated as a no-op.
    """

    value: str
    """The tag to remove."""


@dataclass
class MoveCmd(FileEditCmd):
    """Represents a request to move a file or folder from one location to another.

    This does *not* imply that any links should be rewritten; that is a higher-level operation, which is
    provided by :meth:`notesdir.api.Notesdir.move`.
    """

    dest: Path
    """The new filename."""


@dataclass
class FileQuery:
    """Represents criteria for searching for notes.

    Some methods that take a FileQuery parameter also accept strings as a convenience, which they
    pass to :meth:`parse`

    If multiple criteria are specified, the query should only return notes that satisfy *all* the criteria.
    """

    include_tags: Set[str] = field(default_factory=set)
    """If non-empty, the query should only return files that have *all* of the specified tags."""

    exclude_tags: Set[str] = field(default_factory=set)
    """If non-empty, the query should only return files that have *none* of the specified tags."""

    @classmethod
    def parse(cls, strquery: FileQueryIsh) -> FileQuery:
        """Converts the parameter to a FileQuery, if it isn't one already.

        Query strings are split on spaces. Each part can be one of the following:

        * ``tag:TAG1,TAG2`` - notes must include all the specified tags
        * ``-tag:TAG1,TAG2`` - notes must not include any of the specified tags

        Examples:

        * ``"tag:journal,food -tag:personal"`` - notes that are tagged both "journal" and "food" but not "personal"
        """
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
    """Passed by :meth:`notesdir.api.Notesdir.new` when it is rendering one of a user's templates.

    It is used for passing data in and out of the template.
    """

    dest: Optional[Path] = None
    """The path at which the new file should be created.
    
    If this is set before rendering the template, it is the path the user suggested. But the template can change it,
    and the template's suggestion will take precedence.
    If the path already exists, notesdir will adjust it further to get a unique path before creating the file.
    """
