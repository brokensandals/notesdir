from __future__ import annotations
from pathlib import Path
import re
from datetime import datetime
import toml
from notesdir.accessors.base import SetAttr
from notesdir.accessors.delegating import DelegatingAccessor
from notesdir.store import FSStore, edits_for_rearrange


def filename_for_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r'[^a-z0-9]', '-', title)
    title = re.sub(r'-+', '-', title)
    title = title.strip('-')
    return title


class Error(Exception):
    pass


class Notesdir:
    @classmethod
    def user_config_path(cls) -> Path:
        """Returns the Path to the user's config file, ~/.notesdir.toml"""
        return Path.home().joinpath('.notesdir.toml')

    @classmethod
    def user_default(cls) -> Notesdir:
        """Creates an instance with config loaded from user_config_path().

        Raises Error if there is not a file at that path.
        """
        path = cls.user_config_path()
        if not path.is_file():
            raise Error(f"No config file found at {path}")
        return cls(toml.load(path))

    def __init__(self, config):
        if 'root' not in config:
            raise Error('Config missing key "root"')
        self.config = config
        accessor = DelegatingAccessor()
        self.store = FSStore(Path(config['root']), accessor)

    def move(self, src: Path, dest: Path, *, creation_folders=False) -> Path:
        """Moves a file or directory and updates references to/from it appropriately.

        If dest is a directory, src will be moved into it, using src's filename.
        Otherwise, src is renamed to dest.

        Existing files/directories will never be overwritten; if needed, a numeric
        prefix will be added to the final destination filename to ensure uniqueness.

        If creation_folders is true, then inside the parent of dest (or dest itself if
        dest is a directory), a folder named for the creation year of the file will be
        created (if it does not exist), and inside of that will be a folder named for
        the creation month of the file. The file will be moved into that directory.

        Returns the actual path that src was moved to.
        """
        if not src.exists():
            raise FileNotFoundError(f'File does not exist: {src}')
        if dest.is_dir():
            dest = dest.joinpath(src.name)
        if creation_folders:
            info = self.store.info(src)
            if not (info and info.created):
                raise Error(f'Cannot parse created time from file: {src}')
            destdir = dest.parent.joinpath(str(info.created.year), f'{info.created.month:02}')
            destdir.mkdir(parents=True)
            dest = destdir.joinpath(dest.name)
        basename = dest.name
        prefix = 2
        while dest.exists():
            dest = dest.with_name(f'{prefix}-{basename}')
            prefix += 1
        edits = edits_for_rearrange(self.store, {src: dest})
        self.store.change(edits)
        return dest

    def normalize(self, path: Path) -> Path:
        """Updates metadata and/or moves a file to adhere to conventions.

        If the file does not have a title, one is set based on the filename.
        If the file has a title, the filename is derived from it.
        In either case filename_for_title is applied.

        If the file does not have created set in its metadata, it is set
        based on the ctime of the file.

        The final path of the file is returned.
        """
        if not path.exists():
            raise FileNotFoundError(f'File does not exist: {path}')
        info = self.store.info(path)
        if not info:
            raise Error(f'Cannot parse file: {path}')

        edits = []

        title = info.title or path.stem
        name = f'{filename_for_title(title)}{path.suffix}'
        if not path.name == name:
            path = self.move(path, path.with_name(name))
        if not title == info.title:
            edits.append(SetAttr(path, 'title', title))

        if not info.created:
            stat = path.stat()
            created = datetime.utcfromtimestamp(stat.st_ctime)
            edits.append(SetAttr(path, 'created', created))

        if edits:
            self.store.change(edits)

        return path
