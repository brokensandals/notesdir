"""Defines the API for parsing/changing information like metadata and links in individual files.

The most important class is :class:`Accessor`.
"""

from typing import List

from notesdir.models import AddTagCmd, DelTagCmd, FileInfo, FileEditCmd, ReplaceHrefCmd, SetCreatedCmd, SetTitleCmd


class ParseError(Exception):
    """Raised when an :class:`Accessor` is unable to parse a file."""
    def __init__(self, message: str, path: str, cause: BaseException = None):
        self.message = message
        self.path = path
        self.cause = cause


class ChangeError(Exception):
    """Raised when an :class:`Accessor` is unable to perform a requested change."""
    def __init__(self, message: str, edits: List[FileEditCmd], cause: BaseException = None):
        self.message = message
        self.edits = edits
        self.cause = cause


class UnsupportedChangeError(ChangeError):
    """Raised when an :class:`Accessor` does not support the type of change requested at all."""
    def __init__(self, edit: FileEditCmd):
        super().__init__('Unsupported edit', [edit])


class Accessor:
    """Base class for accessors, which are responsible for reading and writing supported file types.

    Each instance is for working with a single file, specified to the constructor.

    .. attribute:: path
       :type: str

    .. attribute:: edited
       :type: bool

       If True, indicates the instance has unsaved edits for the file.
    """
    def __init__(self, path: str):
        self.path = path
        self._loaded = False
        self.edited = False

    def load(self) -> None:
        """Attempts to parse the file. This does not normally need to be called explicitly.

        It will be called by :meth:`info` when necessary.

        May raise :exc:`ParseError`.
        """
        try:
            self._load()
        except Exception as e:
            self._loaded = False
            raise e
        self._loaded = True

    def info(self) -> FileInfo:
        """Returns details about the file.

        This will not necessarily reload the file from disk if the instance has previously loaded it.

        This will only populate the attributes of FileInfo that are supported by the particular subclass, and
        also will not populate any attributes (such as backlinks) that cannot be derived from the file in isolation.

        May raise :exc:`ParseError`.
        """
        if not self._loaded:
            self.load()
        info = FileInfo(self.path)
        self._info(info)
        return info

    def edit(self, edit: FileEditCmd) -> None:
        """Applies the given change to this instance (but does not save it to the file yet).

        May raise :exc:`ChangeError`.
        Should raise :exc:`UnsupportedChangeError` if the edit is unsupported for this file type
        or invalid for the file.

        Raises :exc:`ValueError` if the ``path`` of the edit does not match the ``path`` of this accessor.
        """
        if not edit.path == self.path:
            raise ValueError(f'Accessor path [{self.path}] is different from path of edit: {edit}')
        if not self._loaded:
            self.load()
        self._edit(edit)

    def _edit(self, edit: FileEditCmd) -> None:
        if isinstance(edit, AddTagCmd):
            self._add_tag(edit)
        elif isinstance(edit, DelTagCmd):
            self._del_tag(edit)
        elif isinstance(edit, ReplaceHrefCmd):
            if not edit.original == edit.replacement:
                self._replace_href(edit)
        elif isinstance(edit, SetCreatedCmd):
            self._set_created(edit)
        elif isinstance(edit, SetTitleCmd):
            self._set_title(edit)

    def save(self) -> bool:
        """Writes any changes from prior calls to :meth:`edit` to the file.

        Returns True if there were changes to save, and False if there were none.
        Raises :meth:`ChangeError` or an IO-related exception if the changes cannot be saved.

        This method may do nothing if :attr:`self.edited` is False.

        This method may overwrite changes on disk that were made since the data was loaded.
        """
        if not self.edited:
            return False
        self._save()
        self.edited = False
        return True

    def _load(self):
        """Subclasses should override this instead of :meth:`load`.

        The base class will then track whether load has been called, so that calls to :meth:`info`
        do result in multiple loads."""
        raise NotImplementedError()

    def _info(self, info: FileInfo) -> None:
        """Subclasses should override this instead of :meth:`info`.

        The base class will ensure :meth:`load` has been called, and create a :class:`FileInfo` instance
        with :attr:`info.path` already set. This method should set the other attributes.
        """
        raise NotImplementedError()

    def _save(self) -> None:
        """Subclasses should override this instead of :meth:`save`.

        The base class will only invoke this method if :attr:`self.edited` is True, and will set it to False afterward.
        """
        raise NotImplementedError()

    def _add_tag(self, edit: AddTagCmd) -> None:
        """Subclasses should override this to support :class:`AddTagCmd` edits.

        The subclass should set :attr:`self.edited` to True if the tag is not already on the file.
        """
        raise UnsupportedChangeError(edit)

    def _del_tag(self, edit: DelTagCmd):
        """Subclasses should override this to support :class:`DelTagCmd` edits.

        The subclass should set :attr:`self.edited` to True unless the tag does not exist on the file.
        """
        raise UnsupportedChangeError(edit)

    def _set_title(self, edit: SetTitleCmd):
        """Subclasses should override this to support :class:`SetTitleCmd` edits.

        The subclass should set :attr:`self.edited` to True unless the new title matches the current title.
        """
        raise UnsupportedChangeError(edit)

    def _set_created(self, edit: SetCreatedCmd):
        """Subclasses should override this to support :class:`SetCreatedCmd` edits.

        The subclass should set :attr:`self.edited` to True unless the new created date matches the existing one.
        """
        raise UnsupportedChangeError(edit)

    def _replace_href(self, edit: ReplaceHrefCmd):
        """Subclasses should override this to support :class:`ReplaceRefCmd` edits.

        The subclass should set :attr:`self.edited` to True if :attr:`edit.original` exists in the file.
        The base class will ensure this method is not called if :attr:`edit.original` == :attr:`edit.replacement`.
        """
        raise UnsupportedChangeError(edit)


class MiscAccessor(Accessor):
    """This accessor can be given the path to any file or folder, or even a nonexistent path.

    Its :meth:`info` method only populates the :attr:`path` field, and no editing or saving is supported."""
    def _load(self) -> None:
        pass

    def _info(self, info: FileInfo) -> None:
        pass

    def _save(self) -> None:
        raise NotImplementedError()
