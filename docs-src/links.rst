Link Management
===============

Notesdir facilitates the use of regular hyperlinks, with relative file paths, for linking between notes or referencing attachments.
The advantage of this over a more specialized syntax is that it allows a wide variety of viewing/editing software to understand the links out-of-the-box.

One challenge to that approach is that if you rename or move a file, links to and from it are broken.
To address this, when the ``notesdir mv`` command moves a file, it also updates all links to it in other files so that they point to the new location.

The list of links to a file (backlinks) can also be accessed from the CLI or API if you want to conduct analysis of the relationships between your notes.

File type support
-----------------

Links **to** any type of file or folder can be detected, as long as the link is **from** a supported file type:

- **Markdown**: links like ``[link text](path/to/file.xyz)`` are recognized, along with some but not all other syntaxes.
  See :class:`notesdir.accessors.markdown.MarkdownAccessor` for more details of what is supported.
- **HTML**: links like ``<a href="path/to/file.xyz">link text</a>`` are recognized, along with references to resources in various elements like ``img``.
  See :class:`notesdir.accessors.html.HTMLAccessor` for more details of what is supported.

Configuration
-------------

When searching for backlinks, notesdir scans all the files it knows about from your configuration - see :class:`notesdir.conf.RepoConf`.
All files (of supported file types) in ``roots`` will be checked, unless they are filtered out by ``skip_parse`` or ``ignore``.

Viewing links and backlinks
---------------------------

Use the ``notesdir info`` command to view links to and from a particular file:

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

In the ``links`` section, the text to the left of the arrow is the actual link as it appears in the file, while the text to the right of the arrow is the absolute path of the target file.
The ``backlinks`` section lists the absolute paths of files that contain links to this file.

Moving files without breaking links
-----------------------------------

Suppose you have this directory tree:

.. code-block:: text

    notes/
        one.md : "I link to [file two](two.md)"
        two.md : "I link to [file one](one.md)"
        subdir/

You can run the following command to move two.md:

.. code-block:: bash

   notesdir mv notes/two.md notes/two.md/subdir/newname.md

Now your directory tree and files will look like this:

.. code-block:: text

    notes/
        one.md : "I link to [file two](subdir/newname.md)"
        subdir/
            newname.md : "I link to [file one](../one.md)"

If you want a list of what files will be changed without actually changing them, use ``notesdir mv --preview``.

Replacing links
---------------

Sometimes you may want to replace links without moving any files.
For example, if you convert an HTML file to Markdown, you would want to find all links to the old ``.html`` file and replace them with links to the new ``.md`` file.
Use the ``relink`` command to do this.
It does not move any files, or even care whether the old or new paths refer to real files.

.. code-block:: bash

   notesdir relink old.html new.md

If you want a list of what files will be changed without actually changing them, use ``notesdir relink --preview``.
