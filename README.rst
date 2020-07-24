About
-----

Notesdir is a command-line tool to help you manage notes that are stored as regular files.
It can assist with:

- Link management
    - update references to and from a file when moving it
    - show links and backlinks for a file
- Metadata management
    - store title, true creation date, and tags in each file via mechanisms appropriate to the file type
    - display metadata in unified format
- Querying
    - look for files with or without specific tags
- Templating
    - write `Mako <https://www.makotemplates.org/>`__ templates for quickly creating new notes
- Organizing
    - write rules in Python for organizing directories based on file metadata or relations between files

Philosophy
----------

- You can use any editors you want.
- Notes don't all have to be the same file format.
  Notesdir can currently parse and update Markdown, HTML, and PDFs; new file type support is straightforward to add; unrecognized file types can coexist peacefully.
- You can organize your files however you want, and reorganize them at will.
- Your notes should remain completely usable without notesdir.
  In particular, links between notes are just regular relative file paths which can be followed by many text editors, terminals, and browsers.
- You should be able to use just the features of notesdir that you want.
  The goal is to be more like a library than a framework.
- Notesdir's functionality is all easy to use programmatically.
  The Python API can be imported into your own scripts.
  The CLI commands also have options to print output as JSON.

Setup
-----

1. Install `Python <https://www.python.org>`__ 3.7 or greater
2. Run :code:`pip3 install notesdir`
3. Create a ``.notesdir.conf.py`` file in your home directory:

.. code-block:: python

    from notesdir.conf import *

    conf = NotesdirConf(
        # SqliteRepo enables caching, which is important if you have more than a few dozen notes.
        # The sqlite database is just a cache: if you delete it, it'll be rebuilt the next time you
        # run notesdir (but that may take a while).
        repo_conf = SqliteRepoConf(
            # List the directories that contain your notes here.
            # These are searched recursively, you should not also list subdirectories.
            root_paths={'/Users/jacob/Zettel'},

            # Specify a path to store the cache in. The file will be created if it does not exist.
            # If you only have a handful of notes, you can use DirectRepoConf instead of SqliteRepoConf,
            # and omit this line.
            cache_path='/Users/jacob/local-only/notesdir-cache.sqlite3'
        ),

        # This is an optional list of path globs where note templates can be found; it's used
        # by the `notesdir new` command.
        template_globs=["/Users/jacob/Zettel/*/templates/*.mako"]
    )

    # This is optional. It determines the behavior of the `notesdir organize` command. This config sets
    # up a couple rules:
    # - If a file has title metadata, use that to set the filename, and use a limited set of characters
    #   in the filename
    # - If you have attachments organized into ".resources" dirs - for example,
    #   a file "foo.md" and "foo.md.resources/bar.png" - make sure the files in the resources dir move
    #   when the main file moves.
    def path_organizer(info):
        path = rewrite_name_using_title(info)
        return resource_path_fn(path) or path

    conf.path_organizer = path_organizer

    # This is optional. It tells notesdir not to parse or edit certain files. I store attachments
    # to notes in directories named like `filename.resources`, and those attachments would never
    # contain metadata or links that I want to query or update, so I skip parsing those.
    # These files can still be moved by `organize`, and backlinks are still tracked for them.
    def skip_parse(parentpath, filename):
        return filename.endswith('.resources')

    conf.repo_conf.skip_parse = skip_parse

That's it!
You can run :code:`notesdir query` to print a list of everything Notesdir currently knows about your notes.
(Which may or may not be very much, until you fill in some metadata.)
It may take a while the first time, while it builds the cache.

See the `full documentation <https://brokensandals.github.io/notesdir/contents.html>`__ for a walkthrough of all the functionality.
