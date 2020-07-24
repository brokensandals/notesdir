from __future__ import annotations
from dataclasses import dataclass, field, replace
import os.path
import re
from typing import Callable, Set, Optional
from notesdir.models import FileInfo, DependentPathFn


def default_ignore(parentpath: str, filename: str) -> bool:
    return filename.startswith('.') or filename.endswith('.icloud')


def default_skip_parse(parentpath: str, filename: str) -> bool:
    return False


def resource_path_fn(path: str) -> Optional[DependentPathFn]:
    """Enables moving files in ``.resources`` directories when the owner moves.

    This is meant for use in a :attr:`NotesdirConf.path_organizer` if you'd like to follow the convention of
    putting attachments for a file in a directory next to the file, with a suffix of ``.resources``. For example,
    an attachment ``cat.png`` for the file ``/notes/foo.md`` would be at ``/notes/foo.md.resources/cat.png``.

    This function lets you ensure that if ``foo.md`` is renamed by your organizer, ``foo.md.resources`` will be too.

    Example usage:

    .. code-block:: python

       def my_path_organizer(info):
           rewrite = resource_path_fn(info.path)
           if rewrite:
               return rewrite
           # put the rest of your organizer rules here
       conf.path_organizer = my_path_organizer
    """
    prev = path
    ancestor = os.path.dirname(path)
    while ancestor and not ancestor == prev:
        if ancestor.endswith('.resources'):
            owner = ancestor[:-10]

            def mkpath(info: FileInfo) -> str:
                resdir = f'{info.path}.resources'
                return os.path.join(resdir, os.path.relpath(path, ancestor))

            return DependentPathFn(owner, mkpath)
        prev = ancestor
        ancestor = os.path.dirname(ancestor)
    return None


def rewrite_name_using_title(info: FileInfo) -> str:
    """If the given info has a title, returns an updated path using that title.

    The following adjustments are made:

    * Title is truncated to 60 characters
    * Characters are converted to lowercase
    * Only the letters a-z and digits 0-9 are kept; all other characters are replaced with dashes
    * Consecutive dashes are collapsed to a single dash
    * Leading and trailing dashes are removed

    For example, for a file at ``/foo/bar.md`` with title "Everything is awful", the path returned would be
    ``/foo/everything-is-awful.md``.

    The file extension from the original path is kept, but note that currently this will not work properly for
    files with multiple extensions (eg ``tar.gz``). That shouldn't be an issue right now since none of the file types
    for which title metadata is supported typically use multiple extensions.

    If there is no title, the path is returned unchanged.

    This is meant to be used as, or as part of, a :attr:`NotesdirConf.path_organizer`.
    """
    if info.title:
        parent, filename = os.path.split(info.path)
        suffix = os.path.splitext(filename)[1]
        title = info.title.lower()[:60]
        title = re.sub(r'[^a-z0-9]', '-', title)
        title = re.sub(r'-+', '-', title)
        title = title.strip('-')
        return os.path.join(parent, f'{title}{suffix}')
    else:
        return info.path


@dataclass
class RepoConf:
    """Base class for repo config. Use a subclass such as :class:`SqliteRepoConf`."""

    root_paths: Set[str]
    """The folders that should be searched (recursively) when querying for notes, finding backlinks, etc.
    
    Must not be empty.
    """

    ignore: Callable[[str, str], bool] = default_ignore
    """Use this to indicate files or folders that should not be processed by notesdir at all.
    
    The first argument is the path to the directory containing the file/folder, and the second argument is
    the filename.
    
    If this function returns True for a given path, neither that path nor any of its child paths
    will be parsed, or returned in any queries, or affected by the ``organize`` command.
    
    The ``mv`` command may still move these files when explicitly instructed to do so or when moving a directory
    containing them, and the ``info`` command will still show backlinks from other (non-ignored) files.
    
    The current default behavior is to ignore all files or folders whose name begins with a period (``.``), and also
    ``.icloud`` files.
    """

    skip_parse: Callable[[str, str], bool] = default_skip_parse
    """Use this to indicate files or folders that should not be parsed (or edited) by notesdir.
    
    The first argument is the path to the directory containing the file/folder, and the second argument is
    the filename.
    
    If this function returns True for a given path, parsing will be skipped for both it and its child paths.
    For such files, only the path and backlinks attributes will be populated on :class:`notesdir.models.FileInfo`.
    
    Unlike :attr:`notesdir.conf.RepoConf.ignore`, unparsed files are still potentially returned in queries and
    affected by the ``organize`` command. Note that parsing is automatically skipped for ignored files. 
    
    The current default behavior does not skip anything.
    """

    preview_mode: bool = False
    """If True, commands that would change notes should instead just print a list of changes to the console.
    
    Instead of setting this in your ``.notesdir.conf.py``, you can pass a ``--preview`` command-line argument to
    relevant commands.
    """

    def instantiate(self):
        raise NotImplementedError("Please use a subclass like SqliteRepoConf instead!")

    def standardize(self):
        return replace(
            self,
            root_paths={os.path.realpath(p) for p in self.root_paths}
        )


@dataclass
class DirectRepoConf(RepoConf):
    """Configures notesdir to access notes without caching, via :class:`notesdir.repos.DirectRepo`."""
    def instantiate(self):
        from notesdir.repos.direct import DirectRepo
        return DirectRepo(self.standardize())


@dataclass
class SqliteRepoConf(DirectRepoConf):
    """Configures notesdir to access notes with caching, via :class:`notesdir.repos.SqliteRepo`."""

    cache_path: str = None
    """Required. Path where the SQLite database file should be stored.
    
    The file will be created if it does not exist.
    The file is only a cache; you can safely delete it when the tool is not running, though you will then have to
    wait for the cache to be rebuilt the next time you run the tool."""

    def instantiate(self):
        from notesdir.repos.sqlite import SqliteRepo
        return SqliteRepo(self.standardize())


@dataclass
class NotesdirConf:
    repo_conf: RepoConf
    """Configures how to access your collection of notes."""

    template_globs: Set[str] = field(default_factory=set)
    """A set of path globs such as ``{"/notes/templates/*.mako"}`` to search for templates.
    
    This is used for the CLI command ``new``, and template-related methods of :class:`notesdir.api.Notesdir`.
    """

    path_organizer: Callable[[FileInfo], str] = lambda info: info.path
    """Defines the rule for rewriting paths used by the ``organize`` command and :meth:`notesdir.api.Notesdir.organize`.

    You can use this to standardize filenames or to organize your files via tags, date, or other criteria.

    For example, the following converts all filenames to lowercase versions of the note title (if any):
    
    .. code-block:: python
    
       import os.path
       def path_organizer(info):
           dirname, filename = os.path.split(info.path)
           suffix = os.path.splitext(filename)[1]
           if info.title:
               return os.path.join(dirname, into.title.lower() + suffix)
           return os.path.join(dirname, filename.lower())

       conf.path_organizer = path_organizer
    
    Here's an example of organizing by important tags:
    
    .. code-block:: python
    
       import os.path
       def path_organizer(info):
           for tag in ['secrets', 'journal', 'grievances']:
               if tag in info.tags:
                   return f'/Users/jacob/notes/{tag}/{os.path.basename(info.path)}'
           return f'/Users/jacob/notes/misc/{os.path.basename(info.path)}'
       
       conf.path_organizer = path_organizer
    
    Some helper functions are provided for use in path organizers:
    
    * :func:`resource_path_fn`
    * :func:`rewrite_name_using_title`
    """

    @classmethod
    def for_user(cls) -> NotesdirConf:
        path = os.path.expanduser(os.path.join('~', '.notesdir.conf.py'))
        if not os.path.exists(path):
            raise Exception(f'You need to create the config file: {path}')
        with open(path, 'r') as file:
            conf_script = file.read()
        context = {}
        exec(conf_script, context)
        if 'conf' not in context or not isinstance(context['conf'], cls):
            raise Exception('You need to assign an instance of NotesdirConf to the variable `conf` '
                            f'in your config file: {path}')
        return context['conf']

    def standardize(self):
        return replace(
            self,
            repo_conf=self.repo_conf.standardize()
        )

    def instantiate(self):
        from notesdir.api import Notesdir
        return Notesdir(self.standardize())
