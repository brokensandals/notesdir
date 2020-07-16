"""Command-line interface for notesdir."""


import argparse
import dataclasses
import json
from operator import itemgetter, attrgetter
from os.path import relpath
from pathlib import Path
from terminaltables import AsciiTable
from notesdir.api import Notesdir
from notesdir.models import FileInfoReq, FileInfo


def _print_file_info(info: FileInfo, fields: FileInfoReq) -> None:
    if fields.path:
        print(f'path: {info.path}')
    if fields.title:
        print(f'title: {info.title}')
    if fields.created:
        print(f'created: {info.created}')
    if fields.tags:
        print(f'tags: {", ".join(sorted(info.tags))}')
    if fields.links:
        print('links:')
        for link in info.links:
            line = f'\t{link.href}'
            referent = link.referent()
            if referent:
                line += f' -> {referent}'
            print(line)
    if fields.backlinks:
        print('backlinks:')
        for link in info.backlinks:
            print(f'\t{link.referrer}')


def _info(args, nd: Notesdir) -> int:
    fields = FileInfoReq.parse(args.fields[0]) if args.fields else FileInfoReq.full()
    info = nd.repo.info(args.path[0], fields)
    if args.json:
        print(json.dumps(info.as_json()))
    else:
        _print_file_info(info, fields)
    return 0


def _new(args, nd: Notesdir) -> int:
    print(nd.new(args.template[0], args.dest))
    return 0


def _mv(args, nd: Notesdir) -> int:
    src = Path(args.src[0])
    dest = Path(args.dest[0])
    moves = nd.move({src: dest})
    if args.json:
        print(json.dumps({str(k): str(v) for k, v in moves.items()}))
    elif not moves == {src: dest}:
        for k, v in moves.items():
            print(f'Moved {k} to {v}')
    return 0


def _org(args, nd: Notesdir) -> int:
    moves = nd.organize()
    if args.json:
        print(json.dumps({str(k): str(v) for k, v in moves.items()}))
    elif moves:
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


def _tag(args, nd: Notesdir) -> int:
    tags = {t.strip() for t in args.tags[0].lower().split(',') if t.strip()}
    nd.add_tags(tags, args.paths)
    return 0


def _tags(args, nd: Notesdir) -> int:
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


def _untag(args, nd: Notesdir) -> int:
    tags = {t.strip() for t in args.tags[0].lower().split(',') if t.strip()}
    nd.remove_tags(tags, args.paths)
    return 0


def _query(args, nd: Notesdir) -> int:
    query = args.query or ''
    infos = [i for i in nd.repo.query(query) if i.path.is_file()]
    if args.fields:
        fields = FileInfoReq.parse(args.fields[0])
    else:
        fields = FileInfoReq(path=True, tags=True, title=True, created=True)
    if args.json:
        infos.sort(key=attrgetter('path'))
        print(json.dumps([i.as_json() for i in infos]))
    elif args.table:
        # TODO make sorting / path resolution consistent with json output
        data = []
        for info in infos:
            row = ()
            if fields.path:
                row += (info.path.name,)
            if fields.title:
                row += (info.title or '',)
            if fields.created:
                row += (info.created.strftime('%Y-%m-%d') if info.created else '',)
            if fields.tags:
                row += ('\n'.join(sorted(info.tags)),)
            if fields.links:
                row += ('\n'.join(sorted({str(relpath(link.referent())) for link in info.links if link.referent()})),)
            if fields.backlinks:
                row += ('\n'.join(sorted({str(relpath(link.referrer)) for link in info.backlinks})),)
            data.append(row)
        data.sort(key=itemgetter(0))
        heading = ()
        if fields.path:
            heading += ('Filename',)
        if fields.title:
            heading += ('Title',)
        if fields.created:
            heading += ('Created',)
        if fields.tags:
            heading += ('Tags',)
        if fields.links:
            heading += ('Link paths',)
        if fields.backlinks:
            heading += ('Backlink paths',)
        data.insert(0, heading)
        table = AsciiTable(data)
        print(table.table)
    else:
        for info in infos:
            print('--------------------')
            _print_file_info(info, fields)
    return 0


def argparser() -> argparse.ArgumentParser:
    fields_help = f'Possible fields are: {", ".join(f.name for f in dataclasses.fields(FileInfoReq))}.'

    parser = argparse.ArgumentParser()
    parser.set_defaults(func=None)

    subs = parser.add_subparsers(title='Commands')

    p_i = subs.add_parser('info', help='Show info about a file, such as metadata and links/backlinks.')
    p_i.add_argument('-f', '--fields', nargs=1,
                     help=f'Comma-separated list of fields to show. {fields_help} By default, all fields are shown.')
    p_i.add_argument('-j', '--json', action='store_true', help='Output as JSON.')
    p_i.add_argument('path', nargs=1)
    p_i.set_defaults(func=_info)

    p_q = subs.add_parser(
        'query',
        help='Query for files. Currently, this only supports searching for files that include or exclude '
             'specified tags. For example, the query "tag:journal,food -tag:personal" would list all '
             'files that have both the "journal" tag and the "food" tag but do not have the "personal" tag.')
    p_q.add_argument('query', nargs='?', help='Query string. If omitted, the query matches all files.')
    p_q.add_argument('-f', '--fields', nargs=1,
                     help=f'Comma-separated list of fields to show. {fields_help} Not all fields are shown by default.')
    p_q_formats = p_q.add_mutually_exclusive_group()
    p_q_formats.add_argument('-j', '--json', help='Output as JSON.', action='store_true')
    p_q_formats.add_argument('-t', '--table', help='Format output as a table.', action='store_true')
    p_q.set_defaults(func=_query)

    p_c = subs.add_parser('new',
                          help='Create new file from a Mako template. You can either specify the path to the template, '
                               'or just give its name without file extensions if it is listed in "templates" in '
                               'your ~/notesdir.conf.py file. '
                               'This command will print the path of the newly created file.')
    p_c.add_argument('template', nargs=1, help='Name or path of template.')
    p_c.add_argument('dest', nargs='?',
                     help='Suggested destination filename. This may be overridden by the template, or adjusted '
                          'if it conflicts with an existing file. A filename will be selected for you if omitted.')
    p_c.set_defaults(func=_new)

    p_mv = subs.add_parser(
        'mv',
        help='Move a file. Any links to the file from other files in your configured notes directories will be '
             'updated to point to the new location, provided the referrers are of supported file types. '
             'Relative links from this file to other files will also be updated, if this file is of a supported file '
             'type.')
    p_mv.add_argument('src', help='File or folder to move.', nargs=1)
    p_mv.add_argument('dest', nargs=1,
                      help='New file path or new parent folder. If the argument is a folder, notesdir will try to '
                           'keep the original filename. In either case, this command will not overwrite an existing '
                           'file; it will adjust the new filename if needed to be unique within the target directory.')
    p_mv.add_argument('-j', '--json', action='store_true',
                      help='Output as JSON. The output is an object whose keys are the paths of files that were '
                           'moved, and whose values are the new paths of those files.')
    p_mv.set_defaults(func=_mv)

    p_org = subs.add_parser(
        'org',
        help='Organize files. All files within the directories configured in conf.repo_conf.root_paths will be '
             'passed to the function defined in conf.path_organizer, and will be moved if it returns a new path. '
             'New folders will be created when necessary and empty folders will be deleted. As with the mv command, '
             'relative links between files will be updated, if the file type of the referrer is supported.')
    p_org.add_argument('-j', '--json', action='store_true',
                       help='Output as JSON. The output is an object whose keys are the paths of files that were '
                            'moved, and whose values are the new paths of those files.')
    p_org.set_defaults(func=_org)

    p_norm = subs.add_parser(
        'norm',
        help='Normalize a file. First, this checks that the title and created date metadata have been stored in '
             'the file in the manner appropriate to its file type. If not, they are updated using the filename '
             'and the best guess at creation date available from the filesystem. Then, the filename is updated '
             'based on the title.')
    p_norm.add_argument('path', help='File to normalize.', nargs=1)
    p_norm.add_argument('-j', '--json', action='store_true', help='Output as JSON, in same format as the `mv` command.')
    p_norm.set_defaults(func=_norm)

    p_tags_add = subs.add_parser(
        'tag',
        help='Add tags to files (if not already present).')
    p_tags_add.add_argument('tags', help='Comma-separated list of tags to add.', nargs=1)
    p_tags_add.add_argument('paths', help='Files to add tags to.', nargs='+')
    p_tags_add.set_defaults(func=_tag)

    p_tags_rm = subs.add_parser(
        'untag',
        help='Remove tags from files (if present).')
    p_tags_rm.add_argument('tags', help='Comma-separated list of tags to remove.', nargs=1)
    p_tags_rm.add_argument('paths', help='Files to remove tags from.', nargs='+')
    p_tags_rm.set_defaults(func=_untag)

    p_tags_count = subs.add_parser(
        'tags',
        help='Show a list of tags and the number of files that have each tag.')
    p_tags_count.add_argument('query', nargs='?',
                              help='Query to filter files by. If omitted, data for all files is shown. The query '
                                   'format is the same as for the `query` command.')
    p_tags_count.add_argument('-j', '--json', action='store_true',
                              help='Output as JSON. The output is an object whose keys are tags and whose values '
                                   'are the number of notes that matched the query and also possess that tag.')
    p_tags_count.set_defaults(func=_tags)

    return parser


def main(args=None) -> int:
    """Runs the tool and returns its exit code.

    args may be an array of string command-line arguments; if absent,
    the process's arguments are used.
    """
    parser = argparser()
    args = parser.parse_args(args)
    if not args.func:
        parser.print_help()
        return 1
    with Notesdir.for_user() as nd:
        return args.func(args, nd)
