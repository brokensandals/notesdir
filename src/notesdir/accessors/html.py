"""Provides the :class:`HTMLAccessor class`."""

from collections import defaultdict
from datetime import datetime
from typing import Set

from bs4 import BeautifulSoup, Tag

from notesdir.accessors.base import Accessor, ChangeError, ParseError
from notesdir.models import AddTagCmd, DelTagCmd, FileInfo, FileEditCmd, SetTitleCmd, SetCreatedCmd, ReplaceHrefCmd,\
    LinkInfo

_DATE_FORMAT = '%Y-%m-%d %H:%M:%S %z'


class HTMLAccessor(Accessor):
    """Responsible for parsing and updating HTML files.

    Current support:

    * Title is stored in the ``<title>`` element.
    * Creation date is stored in the ``<meta name="created">`` element's ``content`` attribute.
    * Tags are stored in the ``<meta name="keywords">`` element's ``content`` attribute, comma-separated.
    * Links can be recognized and updated when they are in the ``a``, ``img``, ``video``, ``audio``, or ``source``
      elements. Note that the ``srcset`` attribute is not currently supported.

    If the file does not at least contain an ``<html>`` element, attempting to add metadata will fail.

    BeautifulSoup4 is used for parsing and updating the files; formatting may be changed during updates.
    """
    def _load(self):
        with open(self.path, 'r') as file:
            try:
                self._page = BeautifulSoup(file, 'lxml')
            except Exception as e:
                raise ParseError('Cannot parse HTML', self.path, e)
        self._title_el = self._page.find('title')
        self._keywords_el = self._page.find('meta', {'name': 'keywords'})
        self._created_el = self._page.find('meta', {'name': 'created'})
        self._link_els = defaultdict(list)
        for a_el in self._page.find_all('a'):
            href = a_el.attrs.get('href', None)
            if href:
                self._link_els[href].append(a_el)
        for source_el in self._page.find_all(['img', 'video', 'audio', 'source']):
            src = source_el.attrs.get('src', None)
            if src:
                self._link_els[src].append(source_el)
            # TODO srcset attribute
        self._head_el = None
        self._html_el = None

    def _info(self, info: FileInfo):
        info.title = self._title()
        info.created = self._created()
        info.tags = self._tags()
        info.links = [LinkInfo(self.path, href) for href in sorted(self._link_els.keys())]

    def _save(self):
        with open(self.path, 'w') as file:
            file.write(str(self._page))

    def _get_head_el(self, edit: FileEditCmd) -> Tag:
        if not self._head_el:
            newel = self._page.new_tag('head')
            self._get_html_el(edit).insert(0, newel)
            self._head_el = newel
        return self._head_el

    def _get_html_el(self, edit: FileEditCmd) -> Tag:
        if not self._html_el:
            self._html_el = self._page.find('html')
            if not self._html_el:
                raise ChangeError(f'File does not contain root <html> element', [edit])
        return self._html_el

    def _tags(self) -> Set[str]:
        if not self._keywords_el:
            return set()
        return {t.strip() for t in self._keywords_el.attrs.get('content', '').lower().split(',')
                if t.strip()}

    def _add_tag(self, edit: AddTagCmd):
        tag = edit.value.lower()
        tags = self._tags()
        if tag in tags:
            return
        if not self._keywords_el:
            newel = self._page.new_tag('meta')
            newel['name' ] = 'keywords'
            self._get_head_el(edit).append(newel)
            self._keywords_el = newel
        tags.add(tag)
        self._keywords_el['content'] = ', '.join(sorted(tags))
        self.edited = True

    def _del_tag(self, edit: DelTagCmd):
        tag = edit.value.lower()
        tags = self._tags()
        if tag not in tags:
            return
        tags.remove(tag)
        self._keywords_el['content'] = ', '.join(sorted(tags))
        self.edited = True

    def _title(self):
        return self._title_el and self._title_el.get_text()

    def _set_title(self, edit: SetTitleCmd):
        # TODO handle setting to None
        self.edited = self.edited or not self._title() == edit.value
        if not self._title_el:
            newel = self._page.new_tag('title')
            self._get_head_el(edit).append(newel)
            self._title_el = newel
        self._title_el.string = edit.value

    def _created(self) -> datetime:
        formatted = self._created_el and self._created_el.attrs.get('content')
        if formatted:
            return datetime.strptime(formatted, _DATE_FORMAT)
        return None

    def _set_created(self, edit: SetCreatedCmd):
        # TODO handle setting to None
        self.edited = self.edited or not self._created() == edit.value
        if not self._created_el:
            newel = self._page.new_tag('meta')
            newel['name'] = 'created'
            self._get_head_el(edit).append(newel)
            self._created_el = newel
        self._created_el['content'] = edit.value.strftime(_DATE_FORMAT)

    def _replace_href(self, edit: ReplaceHrefCmd):
        if edit.original not in self._link_els:
            return False
        self.edited = True
        for link_el in self._link_els[edit.original]:
            if link_el.attrs.get('href', None) == edit.original:
                link_el.attrs['href'] = edit.replacement
            if link_el.attrs.get('src', None) == edit.original:
                link_el.attrs['src'] = edit.replacement
