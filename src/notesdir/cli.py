"""Command-line interface for notesdir."""


import argparse
from pathlib import Path
from notesdir.api import Notesdir


def _mv(args, nd: Notesdir) -> int:
    nd.move(Path(args.src[0]), Path(args.dest[0]))
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
    p_mv.set_defaults(func=_mv)

    args = parser.parse_args(args)
    if not args.func:
        parser.print_help()
        return 1
    nd = Notesdir.user_default()
    return args.func(args, nd)
