"""Command-line interface for notesdir."""


import argparse
from pathlib import Path
from notesdir.api import Notesdir


def _mv(args, nd: Notesdir) -> int:
    src = Path(args.src[0])
    dest = Path(args.dest[0])
    moves = nd.move(src, dest, creation_folders=args.creation_folders)
    if not moves == {src: dest}:
        for k, v in moves.items():
            print(f'Moved {k} to {v}')
    return 0


def _norm(args, nd: Notesdir) -> int:
    path = Path(args.path[0])
    moves = nd.normalize(path)
    if moves:
        for k, v in moves.items():
            print(f'Moved {k} to {v}')
    return 0


def _tags_add(args, nd: Notesdir) -> int:
    tags = {t.strip() for t in args.tags[0].lower().split(',') if t.strip()}
    paths = {Path(p) for p in args.paths}
    nd.add_tags(tags, paths)
    return 0


def _tags_rm(args, nd: Notesdir) -> int:
    tags = {t.strip() for t in args.tags[0].lower().split(',') if t.strip()}
    paths = {Path(p) for p in args.paths}
    nd.remove_tags(tags, paths)
    return 0


def main(args=None) -> int:
    """Runs the tool and returns its exit code.

    args may be an array of string command-line arguments; if absent,
    the process's arguments are used.
    """
    parser = argparse.ArgumentParser()
    parser.set_defaults(func=None)

    subs = parser.add_subparsers(title='Commands')

    p_mv = subs.add_parser(
        'mv',
        help='move file and update references')
    p_mv.add_argument('src', help='file or folder to move', nargs=1)
    p_mv.add_argument('dest', help='new filename or new parent folder', nargs=1)
    p_mv.add_argument('-c', '--creation-folders', action='store_true',
                      help='insert folders like 2020/06 based on creation date of src')
    p_mv.set_defaults(func=_mv)

    p_norm = subs.add_parser(
        'norm',
        help='normalize file')
    p_norm.add_argument('path', help='file to normalize', nargs=1)
    p_norm.set_defaults(func=_norm)

    p_tags_add = subs.add_parser(
        'tags-add',
        help='add tags to files')
    p_tags_add.add_argument('tags', help='comma-separated list of tags', nargs=1)
    p_tags_add.add_argument('paths', help='files to add tags to', nargs='+')
    p_tags_add.set_defaults(func=_tags_add)

    p_tags_rm = subs.add_parser(
        'tags-rm',
        help='remove tags from files')
    p_tags_rm.add_argument('tags', help='comma-separated list of tags', nargs=1)
    p_tags_rm.add_argument('paths', help='files to remove tags from', nargs='+')
    p_tags_rm.set_defaults(func=_tags_rm)

    args = parser.parse_args(args)
    if not args.func:
        parser.print_help()
        return 1
    nd = Notesdir.user_default()
    return args.func(args, nd)
