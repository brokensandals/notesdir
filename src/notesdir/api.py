from __future__ import annotations
from pathlib import Path
import re
from datetime import datetime
from os import PathLike
from typing import Dict, Set, Union
import toml
from notesdir.models import AddTagCmd, DelTagCmd, SetTitleCmd, SetCreatedCmd
from notesdir.rearrange import edits_for_rearrange


def filename_for_title(title: str) -> str:
    title = title.lower()[:60]
    title = re.sub(r'[^a-z0-9]', '-', title)
    title = re.sub(r'-+', '-', title)
    title = title.strip('-')
    return title


def guess_created(path: Path) -> datetime:
    stat = path.stat()
    try:
        return datetime.utcfromtimestamp(stat.st_birthtime)
    except AttributeError:
        return datetime.utcfromtimestamp(stat.st_ctime)


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
        self.config = config
        repo_config = self.config.get('repo', {})
        if 'cache' in repo_config:
            from notesdir.repos.sqlite import SqliteRepo
            self.repo = SqliteRepo(repo_config)
        else:
            from notesdir.repos.direct import DirectRepo
            self.repo = DirectRepo(repo_config)

    def move(self, src: Union[str, bytes, PathLike], dest: Union[str, bytes, PathLike], *, creation_folders=False)\
            -> Dict[Path, Path]:
        """Moves a file or directory and updates references to/from it appropriately.

        If dest is a directory, src will be moved into it, using src's filename.
        Otherwise, src is renamed to dest.

        Existing files/directories will never be overwritten; if needed, a numeric
        prefix will be added to the final destination filename to ensure uniqueness.

        If creation_folders is true, then inside the parent of dest (or dest itself if
        dest is a directory), a folder named for the creation year of the file will be
        created (if it does not exist), and inside of that will be a folder named for
        the creation month of the file. The file will be moved into that directory.

        Returns a dict mapping paths of files that were moved, to their final paths.
        """
        src = Path(src)
        dest = Path(dest)
        if not src.exists():
            raise FileNotFoundError(f'File does not exist: {src}')
        if dest.is_dir():
            dest = dest.joinpath(src.name)
        if creation_folders:
            info = self.repo.info(src)
            created = (info and info.created) or guess_created(src)
            destdir = dest.parent.joinpath(str(created.year), f'{created.month:02}')
            destdir.mkdir(parents=True, exist_ok=True)
            dest = destdir.joinpath(dest.name)

        basename = dest.name
        prefix = 2
        existing = [p.name.lower() for p in dest.parent.iterdir()]
        while True in (n.lower().startswith(dest.name) for n in existing):
            dest = dest.with_name(f'{prefix}-{basename}')
            prefix += 1

        moves = {src: dest}
        # TODO this should probably be configurable
        resdir = src.with_name(f'{src.name}.resources')
        if resdir.exists():
            moves[resdir] = dest.with_name(f'{dest.name}.resources')
            if moves[resdir].exists():
                raise Error(f'Directory already exists: {moves[resdir]}')

        edits = edits_for_rearrange(self.repo, moves)
        self.repo.change(edits)

        return moves

    def normalize(self, path: Union[str, bytes, PathLike]) -> Dict[Path, Path]:
        """Updates metadata and/or moves a file to adhere to conventions.

        If the file does not have a title, one is set based on the filename.
        If the file has a title, the filename is derived from it.
        In either case filename_for_title is applied.

        If the file does not have created set in its metadata, it is set
        based on the birthtime or ctime of the file.

        Returns a dict mapping paths of files that were moved, to their final paths.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f'File does not exist: {path}')
        info = self.repo.info(path)
        if not info:
            raise Error(f'Cannot parse file: {path}')

        edits = []
        moves = {}

        title = info.title or path.stem
        name = f'{filename_for_title(title)}{path.suffix}'
        if not path.name == name:
            moves = self.move(path, path.with_name(name))
            if path in moves:
                path = moves[path]
        if not title == info.title:
            edits.append(SetTitleCmd(path, title))

        if not info.created:
            edits.append(SetCreatedCmd(path, guess_created(path)))

        if edits:
            self.repo.change(edits)

        return moves

    def add_tags(self, tags: Set[str], paths: Set[Union[str, bytes, PathLike]]):
        paths = {Path(p) for p in paths}
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(f'File does not exist: {path}')
            edits = [AddTagCmd(path, t.lower()) for t in tags]
            self.repo.change(edits)

    def remove_tags(self, tags: Set[str], paths: Set[Union[str, bytes, PathLike]]):
        paths = {Path(p) for p in paths}
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(f'File does not exist: {path}')
            edits = [DelTagCmd(path, t.lower()) for t in tags]
            self.repo.change(edits)

    def close(self):
        self.repo.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.repo.close()
