Organizing
==========

With a large number of notes, you probably don't want to rely solely on your folder hierarchy for organizing notes - tags are crucial.
But still, many desktop apps and CLI tools are oriented around the filesystem, so you do want a convenient directory structure.
And what's convenient can change over time.

The ``notesdir organize`` command reorganizes your files based on rules you define.
The rules can set the file's path based on things like its title, creation date, whether it contains certain tags, etc.
This makes it easy to keep a consistent directory structure and also change it quickly.

Whenever it moves a file, it also updates links to and from that file - see :doc:`links`.

Configuration
-------------

The :attr:`notesdir.conf.RepoConf.root_paths` and :attr:`notesdir.conf.RepoConf.ignore` config items determine which files will be processed.
The :attr:`notesdir.conf.NotesdirConf.path_organizer` determines what rules will be applied.
You supply a function which will be called for each file, and return the path at which the file belongs.
(You can also return a :class:`notesdir.models.DependentPathFn` to indicate that the final location depends on whatever the final location for another file ends up being.)

The docs for ``path_organizer`` contain a couple examples and information about some helper functions you can use.
Below is an example from my own config.
This sets up the following rules:

- Using :func:`notesdir.conf.rewrite_name_using_title`, if a title is defined in the file's metadata, the filename is based on that title, with special characters removed
- Using :func:`notesdir.conf.resource_path_fn`, if a file is inside a ``.resources`` directory (which I use to store attachments for notes), it gets moved whenever the note it's attached to gets moved
- Files tagged ``active`` go in a particular directory
- Files tagged ``archive`` or ``source-web`` go in other specific directories, in subdirectories organized by the year and month of each file's creation date (based on the metadata stored inside it, or else filesystem metadata)
- Other files are left where they are

.. code-block:: python

   import os.path
   root ='/Users/jacob/Zettel'
   personal_root = f'{root}/personal'
   personal_active = f'{personal_root}/active'
   personal_archive = f'{personal_root}/archive'
   personal_sources = f'{personal_root}/sources'
   personal_sources_web = f'{personal_sources}/web'

   def created_path(info, folder, name):
    created = info.guess_created()
    return os.path.join(folder, created.strftime('%Y'), created.strftime('%m'), name)

   def path_organizer(info):
       path = rewrite_name_using_title(info)
       resource = resource_path_fn(path)
       if resource:
           return resource

       if path.startswith(personal_root):
           if 'active' in info.tags:
               return os.path.join(personal_active, os.path.basename(path))
           if 'archive' in info.tags:
               return created_path(info, personal_archive, os.path.basename(path))
           if 'source-web' in info.tags:
               return created_path(info, personal_sources_web, os.path.basename(path))

       return path

   conf.path_organizer = path_organizer

Running
-------

To apply the organizational rules, just run:

.. code-block:: bash

   notesdir organize

If you want to see what it's going to do without actually doing it, pass the ``--preview`` option.
