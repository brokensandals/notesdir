from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
from typing import Dict, List
from bs4 import BeautifulSoup, Tag
from notesdir.accessors.base import BaseAccessor, ChangeError, ParseError, UnsupportedChangeError
from notesdir.models import FileInfo, FileEditCmd, SetTitleCmd, SetCreatedCmd, ReplaceRefCmd


_DATE_FORMAT = '%Y-%m-%d %H:%M:%S %z'
TAG_RE = re.compile(r'(?:\s|^)#([a-zA-Z][a-zA-Z\-_0-9]*)\b')


def defaultdict_list():
    return defaultdict(list)


@dataclass
class ParseInfo:
    page: BeautifulSoup
    title_el: Tag = None
    created_el: Tag = None
    ref_els: Dict[str, List[Tag]] = field(default_factory=defaultdict_list)
    pass


class HTMLAccessor(BaseAccessor):
    def parse(self, path: Path) -> FileInfo:
        return self._parse(path)[1]

    def _parse(self, path: Path) -> (ParseInfo, FileInfo):
        with path.open() as file:
            try:
                page = BeautifulSoup(file, 'lxml')
            except Exception as e:
                raise ParseError('Cannot parse HTML', path, e)
        info = FileInfo(path)
        pinfo = ParseInfo(page)
        title_el = page.find('title')
        if title_el:
            info.title = title_el.get_text()
            pinfo.title_el = title_el
        for keywords_el in page.find_all('meta', {'name': 'keywords'}):
            for kw in keywords_el.attrs.get('content', '').lower().split(','):
                tag = kw.strip()
                if tag:
                    info.managed_tags.add(tag)
        body_el = page.find('body')
        if body_el:
            info.unmanaged_tags.update(set(t.lower() for t in TAG_RE.findall(body_el.get_text())))
        created_el = page.find('meta', {'name': 'created'})
        if created_el:
            info.created = datetime.strptime(created_el['content'], _DATE_FORMAT)
            pinfo.created_el = created_el
        for a_el in page.find_all('a'):
            href = a_el.attrs.get('href', None)
            if href:
                info.refs.add(href)
                pinfo.ref_els[href].append(a_el)
        for source_el in page.find_all(['img', 'video', 'audio', 'source']):
            src = source_el.attrs.get('src', None)
            if src:
                info.refs.add(src)
                pinfo.ref_els[src].append(source_el)
            # TODO srcset attribute
        return pinfo, info

    def _change(self, edits: List[FileEditCmd]) -> bool:
        path = edits[0].path
        pinfo, info = self._parse(path)
        changed = False

        html_el = pinfo.page.find('html')
        if not html_el:
            raise ChangeError(f'File does not contain root <html> element', edits)
        head_el = html_el.find('head')
        if not head_el:
            head_el = pinfo.page.new_tag('head')
            html_el.insert(0, head_el)

        for edit in edits:
            if isinstance(edit, ReplaceRefCmd):
                for ref_el in pinfo.ref_els[edit.original]:
                    if ref_el.attrs.get('href', None) == edit.original:
                        ref_el.attrs['href'] = edit.replacement
                        changed = True
                    if ref_el.attrs.get('src', None) == edit.original:
                        ref_el.attrs['src'] = edit.replacement
                        changed = True
            elif isinstance(edit, SetTitleCmd):
                changed = True
                if not pinfo.title_el:
                    pinfo.title_el = pinfo.page.new_tag('title')
                    head_el.append(pinfo.title_el)
                pinfo.title_el.string = edit.value
            elif isinstance(edit, SetCreatedCmd):
                changed = True
                if not pinfo.created_el:
                    pinfo.created_el = pinfo.page.new_tag('meta')
                    pinfo.created_el['name'] = 'created'
                    head_el.append(pinfo.created_el)
                pinfo.created_el['content'] = edit.value.strftime(_DATE_FORMAT)
            else:
                raise UnsupportedChangeError(edit)
        if changed:
            path.write_text(str(pinfo.page))
        return changed
