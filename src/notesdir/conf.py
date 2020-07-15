from __future__ import annotations
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Set, Union
from mako.template import Template
from notesdir.models import FileInfo, PathIsh


_DEFAULT_FILENAME_TEMPLATE = Template("""<%
    import re
    title = info.title.lower()[:60]
    title = re.sub(r'[^a-z0-9]', '-', title)
    title = re.sub(r'-+', '-', title)
    title = title.strip('-')
%>
${title}${info.path.suffix}
""")


def default_ignore(path: Path) -> bool:
    return path.name.startswith('.') or path.suffix == '.icloud'


@dataclass
class RepoConf:
    """Base class for repo config. Use a subclass such as :class:`SqliteRepoConf`."""

    root_paths: Set[PathIsh]
    """The folders that should be searched (recursively) when querying for notes, finding backlinks, etc.
    
    Must not be empty.
    """

    skip_parse: Callable[[Path], bool] = lambda path: False
    """Use this to indicate files that should not be parsed.
    
    Unlike :attr:`ignore`, backlinks are still calculated for these files, they can still be returned by queries,
    and when moving them notesdir will still attempt to update links to them in other files.
    
    If this returns True for a path, that return value applies for all the child paths too.
    
    Nothing is skipped by default.
    """

    ignore: Callable[[Path], bool] = default_ignore
    """Use this to indicate files or folders that should not be processed by notesdir at all.
    
    If this function returns True for a given path, neither that path nor any of its child paths
    will be parsed, or returned in any queries, or affected by the ``org`` command.
    
    The ``mv`` command may still move these files when explicitly instructed to do so or when moving a directory
    containing them.
    
    See also :attr:`skip_parse`.
    
    The current default behavior is to ignore all files or folders whose name begins with a period (``.``), and also
    ``.icloud`` files.
    """

    def instantiate(self):
        raise NotImplementedError("Please use a subclass like SqliteRepoConf instead!")

    def normalize(self):
        return replace(
            self,
            root_paths={Path(p).resolve() for p in self.root_paths}
        )


@dataclass
class DirectRepoConf(RepoConf):
    """Configures notesdir to access notes without caching, via :class:`notesdir.repos.DirectRepo`."""
    def instantiate(self):
        from notesdir.repos.direct import DirectRepo
        return DirectRepo(self.normalize())


@dataclass
class SqliteRepoConf(DirectRepoConf):
    """Configures notesdir to access notes with caching, via :class:`notesdir.repos.SqliteRepo`."""

    cache_path: PathIsh = None
    """Required. Path where the SQLite database file should be stored.
    
    The file will be created if it does not exist.
    The file is only a cache; you can safely delete it when the tool is not running, though you will then have to
    wait for the cache to be rebuilt the next time you run the tool."""

    def instantiate(self):
        from notesdir.repos.sqlite import SqliteRepo
        return SqliteRepo(self.normalize())


@dataclass
class NotesdirConf:
    repo_conf: RepoConf
    """Configures how to access your collection of notes."""

    template_globs: Set[str] = field(default_factory=set)
    """A set of path globs such as ``{"/notes/templates/*.mako"}`` to search for templates.
    
    This is used for the CLI command ``new``, and template-related methods of :class:`notesdir.api.Notesdir`.
    """

    filename_template: Union[str, Template] = _DEFAULT_FILENAME_TEMPLATE
    """Mako template for generating a normalized filename from a :class:`notesdir.models.FileInfo` instance.
    
    The default template truncates the title to 60 characters, downcases it, and ensures it contains only letters,
    numbers, and dashes.
    
    See :meth:`notesdir.api.Notesdir.normalize`
    """

    path_organizer: Callable[[FileInfo], PathIsh] = lambda info: info.path
    """Defines the rule for rewriting paths used by the ``org`` command and :meth:`notesdir.api.Notesdir.organize`.

    You can use this to normalize filenames or to organize your files via tags, date, or other criteria.

    For example, the following converts all filenames to lowercase versions of the note title (if any):
    
    .. code-block:: python
    
       def path_organizer(info):
           if info.title:
               return info.path.with_name(info.title.lower() + info.path.suffix.lower())
           return info.path.with_name(info.path.name.lower())

       conf.path_organizer = path_organizer
    
    Here's an example of organizing by important tags:
    
    .. code-block:: python
    
       def path_organizer(info):
           for tag in ['secrets', 'journal', 'grievances']:
               if tag in info.tags:
                   return f'/Users/jacob/notes/{tag}/{info.path.name}'
           return f'/Users/jacob/notes/misc/{info.path.name}'
       
       conf.path_organizer = path_organizer
    
    The default function does nothing.
    """

    @classmethod
    def for_user(cls) -> NotesdirConf:
        path = Path.home().joinpath('.notesdir.conf.py')
        if not path.exists():
            raise Exception(f'You need to create the config file: {path}')
        context = {}
        exec(Path.home().joinpath('.notesdir.conf.py').read_text(), context)
        if 'conf' not in context or not isinstance(context['conf'], cls):
            raise Exception('You need to assign an instance of NotesdirConf to the variable `conf` '
                            f'in your config file: {path}')
        return context['conf']

    def normalize(self):
        fntemplate = self.filename_template
        return replace(
            self,
            repo_conf=self.repo_conf.normalize(),
            filename_template=fntemplate if isinstance(fntemplate, Template) else Template(fntemplate)
        )

    def instantiate(self):
        from notesdir.api import Notesdir
        return Notesdir(self.normalize())
