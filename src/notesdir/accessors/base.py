from pathlib import Path
from typing import List

from notesdir.models import FileInfo, FileEditCmd, ReplaceRefCmd, SetCreatedCmd, SetTitleCmd


class ParseError(Exception):
    def __init__(self, message: str, path: Path, cause: BaseException = None):
        self.message = message
        self.path = path
        self.cause = cause


class ChangeError(Exception):
    def __init__(self, message: str, edits: List[FileEditCmd], cause: BaseException = None):
        self.message = message
        self.edits = edits
        self.cause = cause


class UnsupportedChangeError(ChangeError):
    def __init__(self, edit: FileEditCmd):
        super().__init__('Unsupported edit', [edit])


class Accessor:
    def __init__(self, path: Path):
        self.path = path
        self._loaded = False
        self.edited = False

    def load(self):
        try:
            self._load()
        except Exception as e:
            self._loaded = False
            raise e
        self._loaded = True

    def info(self) -> FileInfo:
        if not self._loaded:
            self.load()
        info = FileInfo(self.path)
        self._info(info)
        return info

    def edit(self, edit: FileEditCmd):
        if not edit.path == self.path:
            raise ValueError(f'Accessor path [{self.path}] is different from path of edit: {edit}')
        if not self._loaded:
            self.load()
        self._edit(edit)

    def _edit(self, edit: FileEditCmd):
        if isinstance(edit, ReplaceRefCmd):
            if not edit.original == edit.replacement:
                self._replace_ref(edit)
        elif isinstance(edit, SetTitleCmd):
            self._set_title(edit)
        elif isinstance(edit, SetCreatedCmd):
            self._set_created(edit)

    def save(self) -> bool:
        if not self.edited:
            return False
        self._save()
        self.edited = False
        return True

    def _load(self):
        raise NotImplementedError()

    def _info(self, info: FileInfo):
        raise NotImplementedError()

    def _save(self):
        raise NotImplementedError()

    def _set_title(self, edit: SetTitleCmd):
        raise UnsupportedChangeError(edit)

    def _set_created(self, edit: SetCreatedCmd):
        raise UnsupportedChangeError(edit)

    def _replace_ref(self, edit: ReplaceRefCmd):
        raise UnsupportedChangeError(edit)


class MiscAccessor(Accessor):
    def _load(self):
        pass

    def _info(self, info: FileInfo):
        pass

    def _save(self):
        raise NotImplementedError()
