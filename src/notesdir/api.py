from __future__ import annotations
from pathlib import Path
import toml
from notesdir.accessors.delegating import DelegatingAccessor
from notesdir.store import FSStore, edits_for_rearrange


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

    def move(self, src: Path, dest: Path):
        """Moves a file or directory and updates references to/from it appropriately.

        If dest is a directory, src will be moved into it, using src's filename.
        Otherwise, src is renamed to dest.

        Existing files/directories will never be overwritten; if needed, a numeric
        prefix will be added to the final destination filename to ensure uniqueness.

        Returns the actual path that src was moved to.
        """
        if not src.exists():
            raise FileNotFoundError(f'File does not exist: {src}')
        if dest.is_dir():
            dest = dest.joinpath(src.name)
        basename = dest.name
        prefix = 2
        while dest.exists():
            dest = dest.with_name(f'{prefix}-{basename}')
            prefix += 1
        edits = edits_for_rearrange(self.store, {src: dest})
        self.store.change(edits)
        return dest
