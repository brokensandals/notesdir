Python API
==========

You can use notesdir from your own Python scripts by getting an instance of :class:`notesdir.api.Notesdir`.

Example
-------

As an example, here's a script that loops through all your notes to find ones whose titles are palindromes:

.. code-block:: python

   from notesdir.api import Notesdir
   with Notesdir.for_user() as nd:
       for info in nd.repo.query():
           if info.title:
               title = info.title.lower()
               if title == title[::-1]:
                   print(f'{info.title} [{info.path}]')

By default the :meth:`notesdir.repos.base.Repo.query` method returns all notes and a specific subset of available fields, but see the documentation for how to specify a query or request more/fewer fields.

The :meth:`notesdir.api.Notesdir.for_user` method loads the configuration from your ``~/.notesdir.conf.py`` file.
You can also create a :class:`notesdir.conf.NotesdirConf` programmatically instead and create an instance from that.

Important classes
-----------------

- :class:`notesdir.api.Notesdir` - implements the higher-level functionality that's also available in the CLI
- :class:`notesdir.repos.base.Repo` - used for querying for files, retrieving metadata, and changing files; accessible via :attr:`notesdir.api.Notesdir.repo`
- :class:`notesdir.models.FileInfo` - holds file metadata
- :class:`notesdir.models.FileInfoReq` - specifies which fields of a FileInfo should be populated
- :class:`notesdir.models.FileQuery` - specifies filter and sort criteria for a query

Changing files
--------------

To move one or more files and also update all the links to/from those files, use :meth:`notesdir.api.Notesdir.move`.

To change file metadata, use :meth:`notesdir.api.Notesdir.change` or :meth:`notesdir.repos.base.Repo.change`.

If you're using a SQLite cache, the cache is refreshed when :class:`notesdir.repos.sqlite.SqliteRepo` is instantiated (which happens when Notesdir is instantiated).
If your code makes direct changes to files (rather than using one of the change() methods) and also makes use of the Notesdir or Repo classes, you should make sure to call :meth:`notesdir.repos.base.Repo.invalidate` after each change.
