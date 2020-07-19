"""Helper functions for moving files and updating links between them.

Generally, you should use :meth:`notesdir.api.Notesdir.move` or :meth:`notesdir.api.Notesdir.replace_path_hrefs`
instead of using anything in this module directly.
"""

from glob import glob
import os.path
from tempfile import mkstemp
from typing import Dict, Iterator, Set
from urllib.parse import ParseResult, quote, urlunparse, urlparse

from notesdir.models import MoveCmd, ReplaceHrefCmd, FileEditCmd, FileInfoReq
from notesdir.repos.base import Repo


def href_path(src: str, dest: str) -> str:
    """Returns the path to use for a reference from file src to file dest.

    This is a relative path to dest from the directory containing src.

    For example, for src `/foo/bar/baz.md` and dest `/foo/meh/blah.png`,
    returns `../meh/blah.png`.

    src and dest are resolved before calculating the relative path.
    """
    src = os.path.split(os.path.realpath(src))[0]
    dest = os.path.realpath(dest)
    return os.path.relpath(dest, src)


def path_as_href(path: str, into_url: ParseResult = None) -> str:
    """Returns the string to use for referring to the given path in a file.

    This percent-encodes characters as necessary to make the path a valid URL.
    If into_url is provided, it copies every part of that URL except the path
    into the resulting URL.

    Note that if into_url contains a scheme or netloc, the given path must be absolute.
    """
    urlpath = quote(path)
    if into_url:
        if (into_url.scheme or into_url.netloc) and not os.path.isabs(path):
            raise ValueError(f'Cannot put a relative path [{path}]'
                             f'into a URL with scheme or host/port [{into_url}]')
        return urlunparse(into_url._replace(path=urlpath))
    return urlpath


def edits_for_raw_moves(renames: Dict[str, str]) -> Iterator[MoveCmd]:
    """Yields commands that will rename a set of files/folders.

    The keys of the dictionary are the paths to be renamed, and the values
    are what they should be renamed to. If a path appears as both a key and
    as a value, it will be moved to a temporary file as an intermediate
    step.
    """
    phase2 = []
    resolved = {os.path.realpath(s): os.path.realpath(d) for s, d in renames.items()}
    dests = set(resolved.values())
    for dest in dests:
        if dest in resolved and os.path.exists(dest):
            destdir, destname = os.path.split(dest)
            file, tmp = mkstemp(prefix=destname, dir=destdir)
            yield MoveCmd(dest, tmp)
            phase2.append(MoveCmd(tmp, resolved[dest]))
    for src, dest in resolved.items():
        if src not in dests and os.path.exists(src):
            yield MoveCmd(src, dest)
    yield from phase2


def edits_for_path_replacement(referrer: str, hrefs: Set[str], replacement: str) -> Iterator[ReplaceHrefCmd]:
    """Yields commands to replace a file's links to a path with links to another path."""
    for href in hrefs:
        url = urlparse(href)
        newref = path_as_href(href_path(referrer, replacement), url)
        yield ReplaceHrefCmd(referrer, href, newref)


def edits_for_rearrange(store: Repo, renames: Dict[str, str]) -> Iterator[FileEditCmd]:
    """Yields commands that will rename files and update links accordingly.

    The keys of the dictionary are the paths to be renamed, and the values
    are what they should be renamed to. (If a path appears as both a key and
    as a value, it will be moved to a temporary file as an intermediate step.)

    The given store is used to search for files that link to any of the paths that
    are keys in the dictionary, so that ReplaceHrefEditCmd instances can be generated for them.
    The files that are being renamed will also be checked for outbound links,
    and ReplaceRef edits will be generated for those too.

    Source paths may be directories; the directory as a whole will be moved, and links
    to/from all files/folders within it will be updated too.
    """
    to_move = {os.path.realpath(s): os.path.realpath(d) for s, d in renames.items()}
    all_moves = {}
    for src, dest in to_move.items():
        all_moves[src] = dest
        if os.path.isdir(src):
            for path in glob(os.path.join(src, '**', '*'), recursive=True):
                all_moves[path] = os.path.join(dest, os.path.relpath(path, src))

    for src, dest in all_moves.items():
        info = store.info(src, FileInfoReq(path=True, links=True, backlinks=True))
        if info:
            for link in info.links:
                referent = link.referent()
                if not referent:
                    continue
                if referent in all_moves:
                    referent = all_moves[referent]
                url = urlparse(link.href)
                newhref = path_as_href(href_path(dest, referent), url)
                if not link.href == newhref:
                    yield ReplaceHrefCmd(src, link.href, newhref)
        for link in info.backlinks:
            if link.referrer in all_moves:
                continue
            # TODO either pass in all the hrefs at once, or change method to not take in a set
            yield from edits_for_path_replacement(link.referrer, {link.href}, dest)

    yield from edits_for_raw_moves(to_move)
