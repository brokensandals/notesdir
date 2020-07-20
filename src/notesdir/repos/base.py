"""Defines the API for accessing a user's collection of notes.

The most important class is :class:`Repo`.
"""

from datetime import datetime
from typing import Dict, List, Iterator, Set

from notesdir.models import FileInfo, FileEditCmd, MoveCmd, FileQuery, SetTitleCmd, SetCreatedCmd, AddTagCmd,\
    DelTagCmd, ReplaceHrefCmd, FileInfoReq, FileInfoReqIsh, FileQueryIsh, CreateCmd


class Repo:
    """Base class for repos, which are responsible for reading, querying, and changing a user's collection of notes.

    Repo instances use :class:`notesdir.accessors.base.Accessor` instances to read/write individual files,
    but add functionality that requires looking at more than one note in isolation (such as finding backlinks),
    and may also perform caching.
    """
    def info(self, path: str, fields: FileInfoReqIsh = FileInfoReq.internal()) -> FileInfo:
        """Looks up the specified fields for the given file or folder.

        Additional fields might or might not be populated.

        May raise a :exc:`notesdir.accessors.base.ParseError` or IO-related exception, but otherwise will
        always return an instance. If no file or folder exists at the given path, or if the file type is unrecognized,
        it can still populate the ``path`` and ``backlinks`` attributes.
        """
        raise NotImplementedError()

    def change(self, edits: List[FileEditCmd]) -> None:
        """Applies the specified edits and saves the affected files. Changes are applied in order.

        May raise a :exc:`notesdir.accessors.base.ChangeError` or IO-related exception.
        Changes are generally not applied atomically.

        If the repo performs caching, this method will ensure the changes are reflected in the cache, so it is
        not necessary to call :meth:`invalidate` afterward.
        """
        raise NotImplementedError()

    def invalidate(self, only: Set[str] = None) -> None:
        """If the repo uses a cache, this tells it to update the cache before the next read.

        If ``only`` is non-empty, the repo might invalidate only those specific files, for the sake of performance.

        It is not necessary to call this method when you have first created an instance, or after calling
        :meth:`change`, as the repo should invalidate automatically at those times. But if you keep a repo instance around
        while also making direct changes to files yourself, you will need to call this method with the paths of the
        files you changed (or created or deleted).

        This method might only look at filesystem metadata such as modification time, so there may be situations
        in which it fails to notice changes.
        """
        raise NotImplementedError()

    def query(self, query: FileQueryIsh = FileQuery(), fields: FileInfoReqIsh = FileInfoReq.internal())\
            -> Iterator[FileInfo]:
        """Returns the requested fields for all files matching the given query."""
        raise NotImplementedError()

    def tag_counts(self, query: FileQueryIsh = FileQuery()) -> Dict[str, int]:
        """Returns a map of tag names to the number of files matching the query which posses that tag."""
        raise NotImplementedError()

    def close(self) -> None:
        """Release any resources associated with the repo. Should be called when you're done with an instance."""
        pass

    def add_tag(self, path: str, tag: str) -> None:
        """Convenience method equivalent to calling change with one :class`notesdir.models.AddTagCmd`"""
        self.change([AddTagCmd(path, tag)])

    def del_tag(self, path: str, tag: str) -> None:
        """Convenience method equivalent to calling change with one :class`notesdir.models.DelTagCmd`"""
        self.change([DelTagCmd(path, tag)])

    def set_created(self, path: str, created: datetime) -> None:
        """Convenience method equivalent to calling change with one :class:`notesdir.models.SetCreatedCmd`"""
        self.change([SetCreatedCmd(path, created)])

    def set_title(self, path: str, title: str) -> None:
        """Convenience method equivalent to calling change with one :class:`notesdir.models.SetTitleCmd`"""
        self.change([SetTitleCmd(path, title)])

    def replace_href(self, path: str, original: str, replacement: str) -> None:
        """Convenience method equivalent to calling change with one :class:`notesdir.models.ReplaceRefCmd`"""
        self.change([ReplaceHrefCmd(path, original, replacement)])


def _group_edits(edits: List[FileEditCmd]) -> List[List[FileEditCmd]]:
    group = None
    result = []
    for edit in edits:
        if group and edit.path == group[0].path and not isinstance(edit, (CreateCmd, MoveCmd)):
            group.append(edit)
        else:
            group = [edit]
            result.append(group)
    return result
