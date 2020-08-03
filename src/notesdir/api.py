"""Provides the main entry point for using the library, :class:`Notesdir`"""

from __future__ import annotations
from dataclasses import replace
from datetime import datetime
from glob import glob
import os.path
import re
from typing import Dict, Set, Optional, List
from mako.template import Template
from notesdir.conf import NotesdirConf
from notesdir.models import AddTagCmd, DelTagCmd, SetTitleCmd, SetCreatedCmd, FileInfoReq, TemplateDirectives,\
    DependentPathFn, FileInfo, MoveCmd, CreateCmd
from notesdir.rearrange import edits_for_rearrange, edits_for_path_replacement, find_available_name


class Error(Exception):
    pass


class Notesdir:
    """Main entry point for working programmatically with your collection of notes.

    Generally, you should get an instance using the :meth:`Notesdir.for_user` method. Call :meth:`close` when you're
    done with it, or else use it as a context manager.

    This class contains various methods such as :meth:`Notesdir.move` and :meth:`Notesdir.standardize`
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
           nd.change({info.path for info in infos}, add_tags={'personal'})
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

    def replace_path_hrefs(self, original: str, replacement: str) -> None:
        """Finds and replaces links to the original path with links to the new path.

        Note that this does not currently replace links to children of the original path - e.g.,
        if original is "/foo/bar", a link to "/foo/bar/baz" will not be updated.

        No files are moved, and this method does not care whether or not the original or replacement paths
        refer to actual files.
        """
        info = self.repo.info(original, FileInfoReq(path=True, backlinks=True))
        edits = []
        for link in info.backlinks:
            # TODO group links from the same referrer for this call
            edits.extend(edits_for_path_replacement(link.referrer, {link.href}, replacement))
        if edits:
            self.repo.change(edits)

    def move(self, moves: Dict[str, str], *, into_dirs=True, check_exists=True,
             create_parents=False, delete_empty_parents=False) -> Dict[str, str]:
        """Moves files/directories and updates references to/from them appropriately.

        moves is a dict where the keys are source paths that should be moved, and the values are the destinations.
        If a destination is a directory and into_dirs is True, the source will be moved into it,
        using the source's filename; otherwise, the source is renamed to the destination.

        This method tries not to overwrite files; if a destination path already exists, a shortened UUID
        will be appended to the path. You can disable that behavior by setting check_exists=False.

        It's OK for a path to occur as a key and also another key's value. For example,
        ``{'foo': 'bar', 'bar': 'foo'}`` will swap the two files.

        If create_parents is True, any directories in a destination path that do not yet exist will be
        created.

        If delete_empty_parents is True, after moving files out of a directory, if the directory or any of its parent
        directories are empty, they will be deleted. (The root folder or current working directory will not be
        deleted regardless.)

        Returns a dict mapping paths of files that were moved, to their final paths.
        """
        moves = {k: v for k, v in moves.items() if not k == v}
        if not moves:
            return {}

        final_moves = {}
        unavailable = set()
        for src, dest in moves.items():
            if not os.path.exists(src):
                raise FileNotFoundError(f'File does not exist: {src}')
            if os.path.isdir(dest) and into_dirs:
                srcname = os.path.split(src)[1]
                dest = os.path.join(dest, srcname)

            dest = find_available_name(dest, unavailable, src) if check_exists else dest
            final_moves[src] = dest
            unavailable.add(dest)

        edits = list(edits_for_rearrange(self.repo, final_moves))
        for edit in edits:
            if isinstance(edit, MoveCmd):
                edit.create_parents = create_parents
                edit.delete_empty_parents = delete_empty_parents
        self.repo.change(edits)

        return final_moves

    def organize(self) -> Dict[str, str]:
        """Reorganizes files using the function set in :attr:`notesdir.conf.NotesdirConf.path_organizer`.

        For every file in your note directories (defined by :attr:`notesdir.conf.RepoConf.root_paths`), this
        method will call that function with the file's FileInfo, and move the file to the path the function returns.

        Note that the function will only be called for files, not directories. You cannot directly move a directory
        by this method, but you can effectively move one by moving all the files from it to the same new directory.

        This method deletes any empty directories that result from the moves it makes, and creates any directories
        it needs to.

        The FileInfo is retrieved using :meth:`notesdir.models.FileInfoReq.full`.
        """
        infos = self.repo.query('', FileInfoReq.full())
        moves = {}
        move_fns = {}
        info_map = {}
        unavailable = set()
        for info in infos:
            if not os.path.isfile(info.path):
                continue
            info_map[info.path] = info
            dest = self.conf.path_organizer(info)
            if isinstance(dest, DependentPathFn):
                move_fns[info.path] = dest
            else:
                dest = find_available_name(dest, unavailable, info.path)
                if info.path == dest:
                    continue
                moves[info.path] = dest
                unavailable.add(dest)

        def process_fn(src: str):
            dpfn = move_fns[src]
            determinant = dpfn.determinant
            dinfo = info_map.get(determinant, FileInfo(determinant))
            if determinant in move_fns:
                process_fn(determinant)
            if determinant in moves:
                dinfo = replace(dinfo, path=moves[determinant])
            srcdest = dpfn.fn(dinfo)
            del move_fns[src]
            srcdest = find_available_name(srcdest, unavailable, src)
            if src == srcdest:
                return
            moves[src] = srcdest
            unavailable.add(srcdest)

        while move_fns:
            process_fn(next(iter(move_fns)))

        if not moves:
            return {}

        edits = list(edits_for_rearrange(self.repo, moves))
        for edit in edits:
            if isinstance(edit, MoveCmd):
                edit.create_parents = True
                edit.delete_empty_parents = True
        self.repo.change(edits)

        return moves

    def backfill(self) -> (List[str], List[Exception]):
        """Finds all files missing title or created metadata, and attempts to set that metadata.

        Missing titles are set to the filename, minus the file extension.
        Missing created dates are set based on the birthtime or ctime of the file.

        Returns a list of all successfully changed files, and a list of exceptions encountered for other files.
        """
        modified = []
        exceptions = []
        for info in self.repo.query(fields=FileInfoReq(path=True, title=True, created=True)):
            edits = []
            if not info.title:
                _, filename = os.path.split(info.path)
                title, _ = os.path.splitext(filename)
                edits.append(SetTitleCmd(info.path, title))
            if not info.created:
                edits.append(SetCreatedCmd(info.path, info.guess_created()))
            if edits:
                try:
                    self.repo.change(edits)
                    modified.append(info.path)
                except Exception as ex:
                    exceptions.append(ex)
        return modified, exceptions

    def change(self, paths: Set[str], add_tags: Set[str] = set(), del_tags: Set[str] = set(),
               title: Optional[str] = None, created: Optional[datetime] = None) -> None:
        """Applies all the specified changes to the specified paths.

        This is a convenience method that wraps :meth:`notesdir.repos.base.Repo.change`
        """
        edits = []
        for path in paths:
            edits.extend(AddTagCmd(path, t.lower()) for t in add_tags)
            edits.extend(DelTagCmd(path, t.lower()) for t in del_tags)
            if title is not None:
                edits.append(SetTitleCmd(path, title))
            if created is not None:
                edits.append(SetCreatedCmd(path, created))
        self.repo.change(edits)

    def templates_by_name(self) -> Dict[str, str]:
        """Returns paths of note templates that are known based on the config.

        The name is the part of the filename before any `.` character. If multiple templates
        have the same name, the one whose path is lexicographically first will appear in the dict.
        """
        paths = [p for g in self.conf.template_globs for p in glob(g, recursive=True) if os.path.isfile(p)]
        paths.sort()
        return {os.path.split(p)[1].split('.')[0].lower(): p for p in paths}

    def template_for_name(self, name: str) -> Optional[str]:
        """Returns the path to the template for the given name, if one is found.

        If treating the name as a relative or absolute path leads to a file, that file is used.
        Otherwise, the name is looked up from :meth:`Notesdir.templates_by_name`, case-insensitively.
        Returns None if a matching template cannot be found.
        """
        if os.path.isfile(name):
            return name
        else:
            return self.templates_by_name().get(name.lower())

    def new(self, template_name: str, dest: str = None) -> str:
        """Creates a new file using the specified template.

        The template name will be looked up using :meth:`template_for-name`.

        Raises :exc:`FileNotFoundError` if the template cannot be found.

        If dest is not given, a target file name will be generated.

        The following names are defined in the template's namespace:

        * ``nd``: this instance of :class:`Notesdir`
        * ``directives``: an instance of :class:`notesdir.models.TemplateDirectives`
        * ``template_path``: the :class:`pathlib.Path` of the template being rendered

        Returns the path of the created file.
        """
        template_path = self.template_for_name(template_name)
        if not (template_path and os.path.isfile(template_path)):
            raise FileNotFoundError(f'Template does not exist: {template_name}')
        template = Template(filename=os.path.abspath(template_path))
        td = TemplateDirectives(dest=dest if dest is not None else None)
        content = template.render(nd=self, directives=td, template_path=template_path)
        if not td.dest:
            dirname, basename = os.path.split(template_path)
            name, suffix = basename.split('.', 1)[:2]
            suffix = re.sub(r'[\.^]mako', '', suffix)
            td.dest = f'{name}.{suffix}'
        td.dest = os.path.realpath(td.dest)
        td.dest = find_available_name(td.dest, set())
        edits = [CreateCmd(td.dest, contents=content)]
        self.repo.change(edits)
        return td.dest

    def close(self):
        """Closes the associated repo and releases any other resources."""
        self.repo.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.repo.close()
