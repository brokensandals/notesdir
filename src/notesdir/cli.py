"""Command-line interface for notesdir."""


import argparse
import dataclasses
import json
from operator import itemgetter, attrgetter
from os.path import relpath
from pathlib import Path
from urllib.parse import quote
from terminaltables import AsciiTable
from notesdir.api import Notesdir
from notesdir.models import FileInfoReq


def _i(args, nd: Notesdir) -> int:
    fields = FileInfoReq.parse(args.fields[0]) if args.fields else FileInfoReq.full()
    info = nd.repo.info(args.path[0], fields)
    if args.json:
        print(json.dumps(info.as_json()))
    else:
        if fields.path:
            print(f'path: {info.path}')
        if fields.title:
            print(f'title: {info.title}')
        if fields.created:
            print(f'created: {info.created}')
        if fields.tags:
            print(f'tags: {", ".join(sorted(info.tags))}')
        if fields.refs:
            print('refs:')
            for referent, refs in info.path_refs().items():
                for ref in refs:
                    line = f'\t{ref}'
                    if referent:
                        line += f' -> {referent}'
                    print(line)
        if fields.referrers:
            print('referrers:')
            for referrer, refs in info.referrers.items():
                print(f'\t{referrer}')
    return 0


def _c(args, nd: Notesdir) -> int:
    print(nd.create(args.template[0], args.dest))
    return 0


def _mv(args, nd: Notesdir) -> int:
    src = Path(args.src[0])
    dest = Path(args.dest[0])
    moves = nd.move(src, dest, creation_folders=args.creation_folders)
    if args.json:
        print(json.dumps({str(k): str(v) for k, v in moves.items()}))
    elif not moves == {src: dest}:
        for k, v in moves.items():
            print(f'Moved {k} to {v}')
    return 0


def _norm(args, nd: Notesdir) -> int:
    moves = nd.normalize(args.path[0])
    if args.json:
        print(json.dumps({str(k): str(v) for k, v in moves.items()}))
    elif moves:
        for k, v in moves.items():
            print(f'Moved {k} to {v}')
    return 0


def _tags_add(args, nd: Notesdir) -> int:
    tags = {t.strip() for t in args.tags[0].lower().split(',') if t.strip()}
    nd.add_tags(tags, args.paths)
    return 0


def _tags_count(args, nd: Notesdir) -> int:
    query = args.query or ''
    counts = nd.repo.tag_counts(query)
    if args.json:
        print(json.dumps(counts))
    else:
        tags = sorted(counts.keys())
        data = [('Tag', 'Count')] + [(t, counts[t]) for t in tags]
        table = AsciiTable(data)
        table.justify_columns[2] = 'right'
        print(table.table)
    return 0


def _tags_rm(args, nd: Notesdir) -> int:
    tags = {t.strip() for t in args.tags[0].lower().split(',') if t.strip()}
    nd.remove_tags(tags, args.paths)
    return 0


def _q(args, nd: Notesdir) -> int:
    query = args.query or ''
    infos = [i for i in nd.repo.query(query) if i.path.is_file()]
    cwd = Path.cwd().resolve()
    if args.json:
        infos.sort(key=attrgetter('path'))
        print(json.dumps([i.as_json() for i in infos]))
    else:
        # TODO make sorting / path resolution consistent with json output
        data = [(str(relpath(i.path.resolve(), cwd)),
                 i.title or '',
                 i.created.isoformat() if i.created else '',
                 ', '.join(quote(t) for t in sorted(i.tags)))
                for i in infos]
        data.sort(key=itemgetter(0))
        data.insert(0, ('Path', 'Title', 'Created', 'Tags'))
        table = AsciiTable(data)
        table.justify_columns[3] = 'right'
        print(table.table)
    return 0


def main(args=None) -> int:
    """Runs the tool and returns its exit code.

    args may be an array of string command-line arguments; if absent,
    the process's arguments are used.
    """
    fields_help = f'({",".join(f.name for f in dataclasses.fields(FileInfoReq))})'

    parser = argparse.ArgumentParser()
    parser.set_defaults(func=None)

    subs = parser.add_subparsers(title='Commands')

    p_i = subs.add_parser('i', help='show file info')
    p_i.add_argument('-f', '--fields', nargs=1, help=f'comma-separated list of fields to show {fields_help}')
    p_i.add_argument('-j', '--json', action='store_true', help='output as json')
    p_i.add_argument('path', nargs=1)
    p_i.set_defaults(func=_i)

    p_q = subs.add_parser(
        'q',
        help='query for files')
    p_q.add_argument('query', nargs='?')
    p_q.add_argument('-j', '--json', help='output as json', action='store_true')
    p_q.set_defaults(func=_q)

    p_c = subs.add_parser('c', help='create file from template')
    p_c.add_argument('template', nargs=1, help='name or path of template')
    p_c.add_argument('dest', nargs='?', help='suggested destination filename')
    p_c.set_defaults(func=_c)

    p_mv = subs.add_parser(
        'mv',
        help='move file and update references')
    p_mv.add_argument('src', help='file or folder to move', nargs=1)
    p_mv.add_argument('dest', help='new filename or new parent folder', nargs=1)
    p_mv.add_argument('-c', '--creation-folders', action='store_true',
                      help='insert folders like 2020/06 based on creation date of src')
    p_mv.add_argument('-j', '--json', action='store_true', help='output as json')
    p_mv.set_defaults(func=_mv)

    p_norm = subs.add_parser(
        'norm',
        help='normalize file')
    p_norm.add_argument('path', help='file to normalize', nargs=1)
    p_norm.add_argument('-j', '--json', action='store_true', help='output as json')
    p_norm.set_defaults(func=_norm)

    p_tags_add = subs.add_parser(
        't+',
        help='add tags to files')
    p_tags_add.add_argument('tags', help='comma-separated list of tags', nargs=1)
    p_tags_add.add_argument('paths', help='files to add tags to', nargs='+')
    p_tags_add.set_defaults(func=_tags_add)

    p_tags_count = subs.add_parser(
        'tc',
        help='count number of files by tag')
    p_tags_count.add_argument('query', help='query to filter files', nargs='?')
    p_tags_count.add_argument('-j', '--json', help='minimize formatting of output', action='store_true')
    p_tags_count.set_defaults(func=_tags_count)

    p_tags_rm = subs.add_parser(
        't-',
        help='remove tags from files')
    p_tags_rm.add_argument('tags', help='comma-separated list of tags', nargs=1)
    p_tags_rm.add_argument('paths', help='files to remove tags from', nargs='+')
    p_tags_rm.set_defaults(func=_tags_rm)

    args = parser.parse_args(args)
    if not args.func:
        parser.print_help()
        return 1
    with Notesdir.for_user() as nd:
        return args.func(args, nd)
