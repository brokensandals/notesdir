Unreleased
----------

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
