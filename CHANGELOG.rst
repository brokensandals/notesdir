0.0.4 (2020-08-02)
------------------

- Bugfixes
    - For Markdown files, if the document contained additional ``...`` or ``---`` lines after the YAML metadata, the whole document up to that point was incorrectly being treated as part of the metadata.
    - Do not require ``add_tags`` and ``del_tags`` arguments in ``Notesdir.change``.

0.0.3 (2020-07-24)
------------------

- Additions
    - Add ``skip_parse`` configuration option for indicating files that should not be parsed or edited, but should be affected by ``organize``.
- Changes
    - Ignore links and hashtags in fenced code blocks in Markdown.

0.0.2 (2020-07-22)
------------------

- Additions
    - Add :code:`notesdir backfill` for setting title and creation date in bulk.
- Changes
    - Do not rewrite absolute paths unless the target file is also being moved.
- Bugfixes
    - Do not rewrite intra-document links like "``#foo``" to "``.#foo``".
    - Include time zone (UTC) on datetimes loaded from filesystem metadata.

0.0.1 (2020-07-19)
------------------

- Initial release.
