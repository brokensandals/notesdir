from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
from typing import Dict, List
from bs4 import BeautifulSoup, Tag
from notesdir.accessors.base import BaseAccessor, FileInfo, FileEdit


class Error(Exception):
    pass


_DATE_FORMAT = '%Y-%m-%d %H:%M:%S %z'
TAG_RE = re.compile(r'(?:\s|^)#([a-zA-Z][a-zA-Z\-_0-9]*)\b')


def defaultdict_list():
    return defaultdict(list)


@dataclass
class ParseInfo:
    page: BeautifulSoup
    title_tag: Tag = None
    created_tag: Tag = None
    ref_tags: Dict[str, List[Tag]] = field(default_factory=defaultdict_list)
    pass


class HTMLAccessor(BaseAccessor):
    def parse(self, path: Path) -> FileInfo:
        return self._parse(path)[1]

    def _parse(self, path: Path) -> (ParseInfo, FileInfo):
        with path.open() as file:
            try:
                page = BeautifulSoup(file, 'lxml')
            except:
                # TODO log the error somewhere, maybe
                pass
        info = FileInfo(path)
        pinfo = ParseInfo(page)
        title_tag = page.find('title')
        if title_tag:
            info.title = title_tag.get_text()
            pinfo.title_tag = title_tag
        for keywords_tag in page.find_all('meta', {'name': 'keywords'}):
            for kw in keywords_tag.attrs.get('content', '').lower().split(','):
                tag = kw.strip()
                if tag:
                    info.tags.add(tag)
        body_tag = page.find('body')
        if body_tag:
            info.tags.update(set(t.lower() for t in TAG_RE.findall(body_tag.get_text())))
        created_tag = page.find('meta', {'name': 'created'})
        if created_tag:
            info.created = datetime.strptime(created_tag['content'], _DATE_FORMAT)
            pinfo.created_tag = created_tag
        for a_tag in page.find_all('a'):
            href = a_tag.attrs.get('href', None)
            if href:
                info.refs.add(href)
                pinfo.ref_tags[href].append(a_tag)
        for source_tag in page.find_all(['img', 'video', 'audio', 'source']):
            src = source_tag.attrs.get('src', None)
            if src:
                info.refs.add(src)
                pinfo.ref_tags[src].append(source_tag)
            # TODO srcset attribute
        return pinfo, info

    def _change(self, edits: List[FileEdit]) -> bool:
        path = edits[0].path
        pinfo, info = self._parse(path)
        changed = False

        html_tag = pinfo.page.find('html')
        if not html_tag:
            raise Error(f'File does not contain root <html> element: {path}')
        head_tag = html_tag.find('head')
        if not head_tag:
            head_tag = pinfo.page.new_tag('head')
            html_tag.insert(0, head_tag)

        for edit in edits:
            if edit.ACTION == 'replace_ref':
                for ref_tag in pinfo.ref_tags[edit.original]:
                    if ref_tag.attrs.get('href', None) == edit.original:
                        ref_tag.attrs['href'] = edit.replacement
                        changed = True
                    if ref_tag.attrs.get('src', None) == edit.original:
                        ref_tag.attrs['src'] = edit.replacement
                        changed = True
            if edit.ACTION == 'set_attr':
                changed = True
                if edit.key == 'title':
                    if not pinfo.title_tag:
                        pinfo.title_tag = pinfo.page.new_tag('title')
                        head_tag.append(pinfo.title_tag)
                    pinfo.title_tag.string = edit.value
                elif edit.key == 'created':
                    if not pinfo.created_tag:
                        pinfo.created_tag = pinfo.page.new_tag('meta')
                        pinfo.created_tag['name'] = 'created'
                        head_tag.append(pinfo.created_tag)
                    pinfo.created_tag['content'] = edit.value.strftime(_DATE_FORMAT)
        if changed:
            path.write_text(str(pinfo.page))
        return changed
