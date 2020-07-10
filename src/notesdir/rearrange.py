from os.path import relpath
from pathlib import Path
from tempfile import mkstemp
from typing import Dict, Iterator
from urllib.parse import ParseResult, quote, urlunparse, urlparse

from notesdir.models import FileInfo, MoveCmd, ReplaceRefCmd, FileEditCmd
from notesdir.repos.base import Repo


def ref_path(src: Path, dest: Path) -> Path:
    """Returns the path to use for a reference from file src to file dest.

    This is a relative path to dest from the directory containing src.

    For example, for src `/foo/bar/baz.md` and dest `/foo/meh/blah.png`,
    returns `../meh/blah.png`.

    src and dest are resolved before calculating the relative path.
    """
    src = src.resolve().parent
    dest = dest.resolve()
    return Path(relpath(dest, src))


def path_as_ref(path: Path, into_url: ParseResult = None) -> str:
    """Returns the string to use for referring to the given path in a file.

    This percent-encodes characters as necessary to make the path a valid URL.
    If into_url is provided, it copies every part of that URL except the path
    into the resulting URL.

    Note that if into_url contains a scheme or netloc, the given path must be absolute.
    """
    urlpath = quote(str(path))
    if into_url:
        if (into_url.scheme or into_url.netloc) and not path.is_absolute():
            raise ValueError(f'Cannot put a relative path [{path}]'
                             f'into a URL with scheme or host/port [{into_url}]')
        return urlunparse(into_url._replace(path=urlpath))
    return urlpath


def edits_for_raw_moves(renames: Dict[Path, Path]) -> Iterator[MoveCmd]:
    """Yields commands that will rename a set of files/folders.

    The keys of the dictionary are the paths to be renamed, and the values
    are what they should be renamed to. If a path appears as both a key and
    as a value, it will be moved to a temporary file as an intermediate
    step.
    """
    phase2 = []
    resolved = {s.resolve(): d.resolve() for s, d in renames.items()}
    dests = set(resolved.values())
    for dest in dests:
        if dest in resolved and dest.exists():
            file, tmp = mkstemp(prefix=str(dest.name), dir=dest.parent)
            tmp = Path(tmp)
            yield MoveCmd(dest, tmp)
            phase2.append(MoveCmd(tmp, resolved[dest]))
    for src, dest in resolved.items():
        if src not in dests and src.exists():
            yield MoveCmd(src, dest)
    yield from phase2


def edits_for_path_replacement(referrer: FileInfo, original: Path, replacement: Path) -> Iterator[ReplaceRefCmd]:
    """Yields commands to replace one file's references to a path with references to another path.

    For example, if the referrer contains links to "/foo/bar.md" and "/foo/bar.md#section2"
    and original is "/foo/bar.md" and replacement is "/foo/new.md", yields commands for
    updating those links to "/foo/new.md" and "/foo/new.md#section2" respectively.

    Note that this will not update references to children of the given original path, e.g. "/foo/bar.md/baz".
    """
    path = referrer.path
    for ref in referrer.refs_to_path(original):
        url = urlparse(ref)
        newref = path_as_ref(ref_path(path, replacement), url)
        yield ReplaceRefCmd(path, ref, newref)


def edits_for_rearrange(store: Repo, renames: Dict[Path, Path]) -> Iterator[FileEditCmd]:
    """Yields commands that will rename files and update references accordingly.

    The keys of the dictionary are the paths to be renamed, and the values
    are what they should be renamed to. (If a path appears as both a key and
    as a value, it will be moved to a temporary file as an intermediate step.)

    The given store is used to search for files that refer to any of the paths that
    are keys in the dictionary, so that ReplaceRef edits can be generated for them.
    The files that are being renamed will also be checked for outbound relative references,
    and ReplaceRef edits will be generated for those too.

    Source paths may be directories; the directory as a whole will be moved, and references
    to/from all files/folders within it will be updated too.
    """
    to_move = {s.resolve(): d.resolve() for s, d in renames.items()}
    all_moves = {}
    for src, dest in to_move.items():
        all_moves[src] = dest
        if src.is_dir():
            for path in src.glob('**/*'):
                all_moves[path] = dest.joinpath(path.relative_to(src))

    for src, dest in all_moves.items():
        info = store.info(src)
        if info:
            for target, refs in info.path_refs().items():
                if not target:
                    continue
                if target in all_moves:
                    target = all_moves[target]
                for ref in refs:
                    url = urlparse(ref)
                    newref = path_as_ref(ref_path(dest, target), url)
                    if not ref == newref:
                        yield ReplaceRefCmd(src, ref, newref)
        for referrer in store.referrers(src):
            if referrer.resolve() in all_moves:
                continue
            info = store.info(referrer)
            yield from edits_for_path_replacement(info, src, dest)

    yield from edits_for_raw_moves(to_move)
