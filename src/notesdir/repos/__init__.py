"""Handles interaction with a collection of notes.

:class:`notesdir.repos.base.Repo` defines an API.
:class:`notesdir.repos.direct.DirectRepo` is the most basic implementation, while
:class:`notesdir.repos.sqlite.SqliteRepo` is the caching implementation you usually want to use.
"""