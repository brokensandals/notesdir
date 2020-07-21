"""Command-line interface for notesdir."""


import argparse
import dataclasses
from datetime import datetime
import json
from operator import itemgetter, attrgetter
import os.path
import sys
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
    path = nd.new(args.template[0], args.dest)
    if not args.preview:
        print(f'Created {path}')
    return 0


def _change(args, nd: Notesdir) -> int:
    nd.change(set(args.paths),
              add_tags={t.strip() for t in (args.add_tags or [''])[0].lower().split(',') if t.strip()},
              del_tags={t.strip() for t in (args.del_tags or [''])[0].lower().split(',') if t.strip()},
              title=args.title[0] if args.title else None,
              created=datetime.fromisoformat(args.created[0]) if args.created else None)
    return 0


def _mv(args, nd: Notesdir) -> int:
    src = args.src[0]
    dest = args.dest[0]
    moves = nd.move({src: dest})
    if args.json:
        print(json.dumps(moves))
    elif not moves == {src: dest} and not args.preview:
        for k, v in moves.items():
            print(f'Moved {k} to {v}')
    return 0


def _organize(args, nd: Notesdir) -> int:
    moves = nd.organize()
    if args.json:
        print(json.dumps({str(k): str(v) for k, v in moves.items()}))
    elif moves and not args.preview:
        for k, v in moves.items():
            print(f'Moved {k} to {v}')
    return 0


def _backfill(args, nd: Notesdir) -> int:
    changed, errors = nd.backfill()
    if not args.preview:
        for path in changed:
            print(f'Updated {changed}')
        for error in errors:
            print(repr(error), file=sys.stderr)
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


def _relink(args, nd: Notesdir) -> int:
    nd.replace_path_hrefs(args.old[0], args.new[0])
    return 0


def _query(args, nd: Notesdir) -> int:
    query = args.query or ''
    infos = [i for i in nd.repo.query(query) if os.path.isfile(i.path)]
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
                row += (os.path.basename(info.path),)
            if fields.title:
                row += (info.title or '',)
            if fields.created:
                row += (info.created.strftime('%Y-%m-%d') if info.created else '',)
            if fields.tags:
                row += ('\n'.join(sorted(info.tags)),)
            if fields.links:
                row += ('\n'.join(sorted({os.path.relpath(link.referent()) for link in info.links if link.referent()})),)
            if fields.backlinks:
                row += ('\n'.join(sorted({os.path.relpath(link.referrer) for link in info.backlinks})),)
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
    parser.set_defaults(func=None, preview=False)

    subs = parser.add_subparsers(title='Commands')

    p_i = subs.add_parser('info', help='Show info about a file, such as metadata and links/backlinks.')
    p_i.add_argument('-f', '--fields', nargs=1,
                     help=f'Comma-separated list of fields to show. {fields_help} By default, all fields are shown.')
    p_i.add_argument('-j', '--json', action='store_true', help='Output as JSON.')
    p_i.add_argument('path', nargs=1)
    p_i.set_defaults(func=_info)

    p_q = subs.add_parser(
        'query',
        help='Query for files. For full query syntax, see the documentation of '
             'notesdir.models.FileQuery.parse - an example query is "tag:foo sort:title,-created".')
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
    p_c.add_argument('-p', '--preview', action='store_true', help='Print plan but do not create file')
    p_c.set_defaults(func=_new)

    p_change = subs.add_parser('change', help='Update metadata of the specified files.')
    p_change.add_argument('paths', nargs='+', help='Files to update.')
    p_change.add_argument('-a', '--add-tags', nargs=1,
                          help='Comma-separated list of tags to add (if not already present).')
    p_change.add_argument('-d', '--del-tags', nargs=1,
                          help='Comma-separated list of tags to remove (if present).')
    p_change.add_argument('-t', '--title', nargs=1, help='New title for files')
    p_change.add_argument('-c', '--created', nargs=1, help='New created datetime for files, in ISO8601 format')
    p_change.add_argument('-p', '--preview', action='store_true',
                          help='Print changes to be made but do not change files')
    p_change.set_defaults(func=_change)

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
    p_mv.add_argument('-p', '--preview',
                      action='store_true', help='Print changes to be made but do not move or change files')
    p_mv.set_defaults(func=_mv)

    p_org = subs.add_parser(
        'organize',
        help='Organize files. All files within the directories configured in conf.repo_conf.root_paths will be '
             'passed to the function defined in conf.path_organizer, and will be moved if it returns a new path. '
             'New folders will be created when necessary and empty folders will be deleted. As with the mv command, '
             'relative links between files will be updated, if the file type of the referrer is supported.')
    p_org.add_argument('-j', '--json', action='store_true',
                       help='Output as JSON. The output is an object whose keys are the paths of files that were '
                            'moved, and whose values are the new paths of those files.')
    p_org.add_argument('-p', '--preview', action='store_true',
                       help='Print changes to be made but do not move or change files')
    p_org.set_defaults(func=_organize)

    p_backfill = subs.add_parser(
        'backfill',
        help='Backfill missing metadata. All files within the directories configured in conf.repo_conf.root_paths '
             'will be checked for title and created date metadata. If the title is missing, a title is set based '
             'on the filename; if created is missing, it is set based on the file\'s birthtime or ctime. '
             'Errors will be printed but will not result in a nonzero return status, since it is expected that '
             'some files in your notes directories will not be supported by notesdir.')
    p_backfill.add_argument('-p', '--preview', action='store_true',
                            help='Print changes to be made but do not change files')
    p_backfill.set_defaults(func=_backfill)

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

    p_relink = subs.add_parser(
        'relink',
        help='Replace all links to one file with links to another. Note that this does not '
             'currently replace links to children of the original path - e.g., if the '
             'old path is "/foo/bar", a link to "/foo/bar/baz" will not be updated. '
             'No files are moved, and this command does not care whether or not the old '
             'or new paths refer to actual files.')
    p_relink.add_argument('old', nargs=1)
    p_relink.add_argument('new', nargs=1)
    p_relink.add_argument('-p', '--preview', action='store_true',
                          help='Print changes to be made but do not change files')
    p_relink.set_defaults(func=_relink)

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
        if args.preview:
            nd.repo.conf.preview_mode = True
        return args.func(args, nd)
