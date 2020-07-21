Metadata & Querying
===================

Notesdir can read, edit, and search by certain file metadata.
The metadata is stored in the files themselves, using a different mechanism for each file type, to increase interoperability with other software.

Metadata fields
------------------

- **Title**
    - tracking this separately from the filename is useful so that you don't have to worry about special characters in the title
- **Creation date/time**
    - tracking this separately from the date recorded by the filesystem is useful so that it doesn't accidentally get changed or lost
- **Tags**
    - currently, tags are normalized to consist of only lowercase alphanumeric characters and dashes

(see data model in :class:`notesdir.models.FileInfo`)

File type support
-----------------

- **Markdown**: metadata is stored in a YAML header; additionally, hashtags in the text are recognized as tags.
  See :class:`notesdir.accessors.markdown.MarkdownAccessor` for more details and an example document.
- **HTML**: the ``<title>`` and ``<meta>`` elements. are used.
  See :class:`notesdir.accessors.html.HTMLAccessor` for more details.
- **PDF**: the "document info" part of the file, defined by the PDF specification, is used.
  See :class:`notesdir.accessors.pdf.PDFAccessor` for more details.

Viewing metadata
----------------

Use the ``notesdir info`` command to view the metadata for a file:

.. code-block:: bash

   notesdir info philosophy-of-language-the-classics-explained.md

The output looks like this (alternatively, pass ``-j`` to get JSON output):

.. code-block:: text

    path: /Users/jacob/Zettel/personal/active/philosophy-of-language-the-classics-explained.md
    title: Philosophy of Language: The Classics Explained
    created: 2020-06-18 05:33:35.183691
    tags: book, language, nonfiction, philosophy, unit
    links:
            ../archive/2020/06/frege-on-sense-and-reference-mcginn.md -> /Users/jacob/Zettel/personal/archive/2020/06/frege-on-sense-and-reference-mcginn.md
            ../archive/2020/07/kripke-on-names.md -> /Users/jacob/Zettel/personal/archive/2020/07/kripke-on-names.md
            ../archive/2020/07/russell-on-definite-descriptions-mcginn.md -> /Users/jacob/Zettel/personal/archive/2020/07/russell-on-definite-descriptions-mcginn.md
    backlinks:
            /Users/jacob/Zettel/personal/archive/2020/06/frege-on-sense-and-reference-mcginn.md
            /Users/jacob/Zettel/personal/archive/2020/07/kripke-on-names.md
            /Users/jacob/Zettel/personal/archive/2020/07/russell-on-definite-descriptions-mcginn.md

Changing metadata
-----------------

Markdown and HTML file metadata can easily be changed in a text editor, and PDF metadata can be changed with various programs.

Notesdir provides a uniform interface for changing metadata in all the file types it supports, which may be more convenient sometimes:

.. code-block:: bash

   notesdir change --add-tags tag1,tag2 my-file.md
   notesdir change --del-tags tag1,tag2 my-file.md
   notesdir change --title 'My Fantastic File!' my-file.md
   notesdir change --created '2012-04-05' my-file.md

Querying
--------

While you'll probably want to use your operating system & text editor's facilities for most searching, notesdir does provide a supplementary query mechanism.

Currently, only filtering by tags is supported, and sorting by various fields is supported.

See :meth:`notesdir.models.FileQuery.parse` for the full query syntax.

.. code-block:: bash

   notesdir query 'tag:journal -tag:food,personal sort:-created'

.. code-block:: text

   --------------------
   path: /Users/jacob/Zettel/personal/archive/2020/07/way-too-much-piano.pdf
   title: way too much piano
   created: 2020-07-14 08:21:39+00:00
   tags: journal
   --------------------
   path: /Users/jacob/Zettel/personal/archive/2020/07/help-i-can-t-sleep.pdf
   title: help I can’t sleep
   created: 2020-07-07 15:49:33+00:00
   tags: journal
   --------------------
   path: /Users/jacob/Zettel/personal/active/goals-2020-07.md
   title: Goals 2020-07
   created: 2020-07-01 05:59:37.518044
   tags: journal, monthly-goals
   ...

(JSON output and table-formatted output are also supported, and you can return more or fewer fields using the ``-f`` parameter.)

Tag statistics
--------------

There is a command to view all your tags and how many notes are tagged with them:

.. code-block:: bash

   notesdir tags

.. code-block:: text

   +--------------------------+-------+
   | Tag                      | Count |
   +--------------------------+-------+
   | abandoned                | 12    |
   | academic                 | 11    |
   | agriculture              | 1     |
   | alcohol                  | 1     |
   | algebra                  | 2     |
   | animals                  | 2     |
   | animation                | 6     |
   ...

You can also supply a query, to see stats for just the notes matching the query:

.. code-block:: bash

   notesdir tags tag:sci-fi

.. code-block:: text

   +------------------------+-------+
   | Tag                    | Count |
   +------------------------+-------+
   | animation              | 2     |
   | archive                | 3     |
   | biography              | 1     |
   | book                   | 58    |
   | comic                  | 15    |
   | fantasy                | 14    |
   | fiction                | 145   |
   ...

Backfilling title & creation date
---------------------------------

This command will add title and/or creation date to all files (of supported file types) that are missing them:

.. code-block:: bash

   notesdir backfill

Missing titles are set to the filename, without the extension.
Missing creation dates are set based on the filesystem's metadata about the file.
