from datetime import datetime
from pathlib import Path
import re
from typing import List
from bs4 import BeautifulSoup
from notesdir.accessors.base import BaseAccessor, FileInfo, FileEdit


_DATE_FORMAT = '%Y-%m-%d %H:%M:%S %z'
TAG_RE = re.compile(r'(?:\s|^)#([a-zA-Z][a-zA-Z\-_0-9]*)\b')


class HTMLAccessor(BaseAccessor):
    def parse(self, path: Path) -> FileInfo:
        with path.open() as file:
            try:
                page = BeautifulSoup(file)
            except:
                # TODO log the error somewhere, maybe
                pass
        info = FileInfo(path)
        title_tag = page.find('title')
        if title_tag:
            info.title = title_tag.get_text()
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
        for a_tag in page.find_all('a'):
            href = a_tag.attrs.get('href', None)
            if href:
                info.refs.add(href)
        for img_tag in page.find_all('img'):
            src = img_tag.attrs.get('src', None)
            if src:
                info.refs.add(src)
        return info

    def _change(self, edits: List[FileEdit]) -> bool:
        pass
