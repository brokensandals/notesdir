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
3. Create a ``.notesdir.toml`` file in your home directory:

.. code-block:: toml

    # The following line is the only strictly required one. It's a list of directories
    # containing your notes. Directories are searched recursively, so for example if
    # you list "/Users/jacob/Zettel" you do not need to list "/Users/jacob/Zettel/personal".
    repo.roots = ["/Users/jacob/Zettel"]

    # The following line is optional, but it's very important if you have hundreds or thousands
    # of notes. It causes notesdir to keep a cache of note metadata at the specified location.
    # The cache is updated each time you run a notesdir command, by comparing file modification
    # times against the cached values. It's always safe to delete the cache file; it will just
    # be rebuilt the next time you run notesdir.
    repo.cache = "/Users/jacob/local-only/notesdir-cache.sqlite3"

    # This is an optional list of regular expressions that will be matched against
    # the paths of files inside the the roots you specified above. Notesdir will not
    # attempt to parse metadata from any files that match any of these.
    # The 'resources' regex is recommended if you follow the convention of, for example,
    # putting attachments for the note "foo.md" in a folder called "foo.md.resources".
    # Skipping parsing for those attachments can improve performance, and likely doesn't
    # hurt since you probably only care about the metadata attached to the note itself.
    repo.noparse = ["\\.resources(\\/.*)?$", "\\.icloud$"]

    # The following line is optional. Add it if you want to create note templates;
    # it's a list of file globs indicating where your template files will be.
    templates = ["/Users/jacob/Zettel/*/templates/*.mako"]

That's it!
You can run :code:`notesdir q` to print a list of everything Notesdir currently knows about your notes.
It may take a while the first time, while it builds the cache.