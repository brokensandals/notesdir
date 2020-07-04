import re
from collections import defaultdict
from datetime import datetime

from bs4 import BeautifulSoup, Tag

from notesdir.accessors.base import Accessor, ChangeError, ParseError
from notesdir.models import FileInfo, FileEditCmd, SetTitleCmd, SetCreatedCmd, ReplaceRefCmd

_DATE_FORMAT = '%Y-%m-%d %H:%M:%S %z'
TAG_RE = re.compile(r'(?:\s|^)#([a-zA-Z][a-zA-Z\-_0-9]*)\b')


class HTMLAccessor(Accessor):
    def _load(self):
        with self.path.open() as file:
            try:
                self._page = BeautifulSoup(file, 'lxml')
            except Exception as e:
                raise ParseError('Cannot parse HTML', self.path, e)
        self._title_el = self._page.find('title')
        self._keywords_els = self._page.find_all('meta', {'name': 'keywords'})
        body_el = self._page.find('body')
        if body_el:
            self._unmanaged_tags = {t.lower() for t in TAG_RE.findall(body_el.get_text())}
        self._created_el = self._page.find('meta', {'name': 'created'})
        self._ref_els = defaultdict(list)
        for a_el in self._page.find_all('a'):
            href = a_el.attrs.get('href', None)
            if href:
                self._ref_els[href].append(a_el)
        for source_el in self._page.find_all(['img', 'video', 'audio', 'source']):
            src = source_el.attrs.get('src', None)
            if src:
                self._ref_els[src].append(source_el)
            # TODO srcset attribute
        self._head_el = None
        self._html_el = None

    def _info(self, info: FileInfo):
        info.title = self._title()
        info.created = self._created()
        for kwel in self._keywords_els:
            for kw in kwel.attrs.get('content', '').lower().split(','):
                tag = kw.strip()
                if tag:
                    info.managed_tags.add(tag)
        info.unmanaged_tags = self._unmanaged_tags.copy()
        info.refs.update(self._ref_els.keys())

    def _save(self):
        self.path.write_text(str(self._page))

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

    def _replace_ref(self, edit: ReplaceRefCmd):
        if edit.original not in self._ref_els:
            return False
        self.edited = True
        for ref_el in self._ref_els[edit.original]:
            if ref_el.attrs.get('href', None) == edit.original:
                ref_el.attrs['href'] = edit.replacement
            if ref_el.attrs.get('src', None) == edit.original:
                ref_el.attrs['src'] = edit.replacement
