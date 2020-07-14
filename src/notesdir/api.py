"""Provides the main entry point for using the library, :class:`Notesdir`"""

from __future__ import annotations
from dataclasses import replace
from glob import glob
from pathlib import Path
import re
from typing import Dict, Set, Optional, Iterable
from mako.template import Template
from notesdir.conf import NotesdirConf
from notesdir.models import AddTagCmd, DelTagCmd, SetTitleCmd, SetCreatedCmd, FileInfoReq, PathIsh, TemplateDirectives
from notesdir.rearrange import edits_for_rearrange, edits_for_path_replacement


def _find_available_name(dest: Path, also_unavailable: Iterable[Path] = set()) -> Path:
    basename = dest.name
    prefix = 2
    existing = [p.name.lower() for p in dest.parent.iterdir()]
    existing += [p.name.lower() for p in also_unavailable if p.resolve().parent == dest.resolve().parent]
    while True in (n.lower().startswith(dest.name.lower()) for n in existing):
        dest = dest.with_name(f'{prefix}-{basename}')
        prefix += 1
    return dest


class Error(Exception):
    pass


class Notesdir:
    """Main entry point for working programmatically with your collection of notes.

    Generally, you should get an instance using the :meth:`Notesdir.for_user` method. Call :meth:`close` when you're
    done with it, or else use it as a context manager.

    This class contains various methods such as :meth:`Notesdir.move` and :meth:`Notesdir.normalize`
    for performing high-level operations. The :attr:`repo` attribute, which is an instance of
    :class:`notesdir.repos.base.Repo`, provides additional operations, some lower-level.

    .. attribute:: conf
       :type: notesdir.conf.NotesdirConf

       Typically loaded from the variable ``conf`` in the file ``~/.notesdir.conf.py``

    .. attribute:: repo
       :type: notesdir.repos.base.Repo

    Here's an example of how to use this class. This would add the tag "personal" to every note tagged with "journal".

    .. code-block:: python

       from notesdir.api import Notesdir
       with Notesdir.for_user() as nd:
           infos = nd.repo.query('tag:journal', 'path')
           nd.add_tags({'personal'}, {info.path for info in infos})
    """

    @staticmethod
    def for_user() -> Notesdir:
        """Creates an instance using the user's ``~/.notesdir.conf.py`` file.

        Raises :exc:`Exception` if it does not exist or does not define configuration.
        """
        return NotesdirConf.for_user().instantiate()

    def __init__(self, conf: NotesdirConf):
        self.conf = conf
        self.repo = conf.repo_conf.instantiate()

    def replace_path_hrefs(self, original: PathIsh, replacement: PathIsh) -> None:
        """Finds and replaces links to the original path with links to the new path.

        Note that this does not currently replace links to children of the original path - e.g.,
        if original is "/foo/bar", a link to "/foo/bar/baz" will not be updated.

        No files are moved, and this method does not care whether or not the original or replacement paths
        refer to actual files.
        """
        info = self.repo.info(original, FileInfoReq(path=True, backlinks=True))
        replacement = Path(replacement)
        edits = []
        for link in info.backlinks:
            # TODO group links from the same referrer for this call
            edits.extend(edits_for_path_replacement(link.referrer, {link.href}, replacement))
        if edits:
            self.repo.change(edits)

    def move(self, moves: Dict[PathIsh], *, creation_folders=False) -> Dict[Path, Path]:
        """Moves files/directories and updates references to/from them appropriately.

        moves is a dict where the keys are source paths that should be moved, and the values are the destinations.
        If a destination is a directory, the source will be moved into it, using the source's filename;
        otherwise, the source is renamed to the destination.

        Existing files/directories will never be overwritten; if needed, a numeric
        prefix will be added to the final destination filename to ensure uniqueness.

        If creation_folders is true, then inside the parent of each destination (or the destination itself if
        it is a directory), a folder named for the creation year of the file will be
        created (if it does not exist), and inside of that will be a folder named for
        the creation month of the file. The file will be moved into that directory.

        Returns a dict mapping paths of files that were moved, to their final paths.
        """
        moves = {Path(src): Path(dest) for src, dest in moves.items()}
        final_moves = {}
        for src, dest in moves.items():
            if not src.exists():
                raise FileNotFoundError(f'File does not exist: {src}')
            if dest.is_dir():
                dest = dest.joinpath(src.name)
            if creation_folders:
                info = self.repo.info(src)
                created = info.guess_created()
                destdir = dest.parent.joinpath(str(created.year), f'{created.month:02}')
                destdir.mkdir(parents=True, exist_ok=True)
                dest = destdir.joinpath(dest.name)

            dest = _find_available_name(dest, final_moves.values())
            final_moves[src] = dest

            # TODO this should probably be configurable
            resdir = src.with_name(f'{src.name}.resources')
            if resdir.exists():
                final_moves[resdir] = dest.with_name(f'{dest.name}.resources')
                if final_moves[resdir].exists():
                    # The _find_available_name check should prevent this from happening, but just to be safe...
                    raise Error(f'Directory already exists: {final_moves[resdir]}')

        edits = edits_for_rearrange(self.repo, final_moves)
        self.repo.change(edits)

        return final_moves

    def normalize(self, path: PathIsh) -> Dict[Path, Path]:
        """Updates metadata and/or moves a file to adhere to conventions.

        If the file does not have a title, one is set based on the filename.
        If the file has a title, the filename is derived from it.
        In either case, the ``filename_template`` from the config is applied. The name ``info`` will be set in the
        template's namespace to the :class:`notesdir.models.FileInfo` object. ``.strip()`` is called on the template's
        result.

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
        name = self.conf.filename_template.render(info=replace(info, title=title)).strip()
        if not path.name == name:
            moves = self.move({path: path.with_name(name)})
            if path in moves:
                path = moves[path]
                info = self.repo.info(path)
        if not title == info.title:
            edits.append(SetTitleCmd(path, title))

        if not info.created:
            edits.append(SetCreatedCmd(path, info.guess_created()))

        if edits:
            self.repo.change(edits)

        return moves

    def add_tags(self, tags: Set[str], paths: Set[PathIsh]) -> None:
        """Adds (if not already present) the given set of tags to each of the given files.

        If some of the files are of unknown types or types for which tags are
        not supported, an :exc:`notesdir.accessors.base.UnsupportedChangeError` will be raised. In that case,
        the tags may or may not have been added to some or all of the other files.
        """
        paths = {Path(p) for p in paths}
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(f'File does not exist: {path}')
            edits = [AddTagCmd(path, t.lower()) for t in tags]
            self.repo.change(edits)

    def remove_tags(self, tags: Set[str], paths: Set[PathIsh]) -> None:
        """Removes (if present) the given set of tags from each of the given files.

        If some of the files are of unknown types or types for which tags are
        not supported, an :exc:`notesdir.accessors.base.UnsupportedChangeError` will be raised. In that case,
        the tags may or may not have been removed from some or all of the other files.
        """
        paths = {Path(p) for p in paths}
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(f'File does not exist: {path}')
            edits = [DelTagCmd(path, t.lower()) for t in tags]
            self.repo.change(edits)

    def templates_by_name(self) -> Dict[str, Path]:
        """Returns paths of note templates that are known based on the config.

        The name is the part of the filename before any `.` character. If multiple templates
        have the same name, the one whose path is lexicographically first will appear in the dict.
        """
        paths = [Path(p) for g in self.conf.template_globs for p in glob(g, recursive=True) if Path(p).is_file()]
        paths.sort()
        return {p.name.split('.')[0].lower(): p for p in paths}

    def template_for_name(self, name: str) -> Optional[Path]:
        """Returns the path to the template for the given name, if one is found.

        If treating the name as a relative or absolute path leads to a file, that file is used.
        Otherwise, the name is looked up from :meth:`Notesdir.templates_by_name`, case-insensitively.
        Returns None if a matching template cannot be found.
        """
        path = Path(name)
        if path.is_file():
            return path
        else:
            return self.templates_by_name().get(name.lower())

    def new(self, template_name: PathIsh, dest: PathIsh = None) -> Path:
        """Creates a new file using the specified template.

        If the template name is a str, it will be looked up using template_for_name.

        Raises :exc:`FileNotFoundError` if the template cannot be found.

        If dest is not given, a target file name will be generated. Regardless, the :meth:`Notesdir.norm` method
        will be used to normalize the final filename.

        The following names are defined in the template's namespace:

        * ``nd``: this instance of :class:`Notesdir`
        * ``directives``: an instance of :class:`notesdir.models.TemplateDirectives`
        * ``template_path``: the :class:`pathlib.Path` of the template being rendered

        Returns the path of the created file.
        """
        template_path = self.template_for_name(template_name) if isinstance(template_name, str) else Path(template_name)
        if not (template_path and template_path.is_file()):
            raise FileNotFoundError(f'Template does not exist: {template_name}')
        template = Template(filename=str(template_path.resolve()))
        td = TemplateDirectives(dest=Path(dest) if dest is not None else None)
        content = template.render(nd=self, directives=td, template_path=template_path)
        if not td.dest:
            name, suffix = template_path.name.split('.', 1)[:2]
            suffix = re.sub(r'[\.^]mako', '', suffix)
            td.dest = Path(f'{name}.{suffix}')
        td.dest = _find_available_name(td.dest)
        td.dest.write_text(content)
        changed = {td.dest}
        if td.create_resources_dir:
            resdir = td.dest.with_name(f'{td.dest.name}.resources')
            resdir.mkdir()
            changed.add(resdir)
        self.repo.refresh(changed)
        return self.normalize(td.dest).get(td.dest, td.dest)

    def close(self):
        """Closes the associated repo and releases any other resources."""
        self.repo.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.repo.close()
