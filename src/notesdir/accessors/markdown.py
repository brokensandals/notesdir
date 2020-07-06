import re
from io import StringIO
from typing import Set, Tuple

import yaml

from notesdir.accessors.base import Accessor
from notesdir.models import AddTagCmd, DelTagCmd, FileInfo, SetTitleCmd, SetCreatedCmd, ReplaceRefCmd

YAML_META_RE = re.compile(r'(?ms)(\A---\n(.*)\n(---|\.\.\.)\s*\r?\n)?(.*)')
TAG_RE = re.compile(r'(?:\s|^)#([a-zA-Z][a-zA-Z\-_0-9]*)\b')
INLINE_REF_RE = re.compile(r'\[.*?\]\((\S+?)\)')
REFSTYLE_REF_RE = re.compile(r'(?m)^\[.*?\]:\s*(\S+)')


def extract_meta(doc) -> Tuple[dict, str]:
    meta = {}
    match = YAML_META_RE.match(doc)
    if match.groups()[1]:
        meta = yaml.safe_load(match.groups()[1])
    body = match.groups()[3]
    return meta, body


def extract_tags(doc) -> Set[str]:
    return set(t.lower() for t in TAG_RE.findall(doc))


def extract_refs(doc) -> Set[str]:
    return set(INLINE_REF_RE.findall(doc) + REFSTYLE_REF_RE.findall(doc))


def replace_ref(doc: str, src: str, dest: str) -> str:
    escaped_src = re.escape(src)

    def inline_replacement(match):
        return f'{match.group(1)}({dest})'

    def refstyle_replacement(match):
        return f'{match.group(1)}{dest}{match.group(2)}'

    inline = rf'(\[.*\])\({escaped_src}\)'
    doc = re.sub(inline, inline_replacement, doc)
    refstyle = rf'(?m)(^\[.*\]:\s*){escaped_src}(\s|$)'
    doc = re.sub(refstyle, refstyle_replacement, doc)
    return doc


class MarkdownAccessor(Accessor):
    def _load(self):
        text = self.path.read_text()
        self.meta, self.body = extract_meta(text)
        self.refs = extract_refs(self.body)
        self.unmanaged_tags = extract_tags(self.body)

    def _info(self, info: FileInfo):
        info.title = self.meta.get('title')
        info.created = self.meta.get('created')
        info.tags = {k.lower() for k in self.meta.get('keywords', [])}.union(self.unmanaged_tags)
        info.refs = self.refs.copy()

    def _save(self):
        if self.meta:
            sio = StringIO()
            yaml.safe_dump(self.meta, sio)
            text = f'---\n{sio.getvalue()}...\n{self.body}'
        else:
            text = self.body
        self.path.write_text(text)

    def _add_tag(self, edit: AddTagCmd):
        tag = edit.value.lower()
        # TODO probably isn't great that this will duplicate a tag into the keywords when it's
        #      already in the body as a hashtag
        self.edited = self.edited or tag not in self.meta.get('keywords', [])
        if 'keywords' in self.meta:
            self.meta['keywords'].append(tag)
            self.meta['keywords'].sort()
        else:
            self.meta['keywords'] = [tag]

    def _del_tag(self, edit: DelTagCmd):
        tag = edit.value.lower()
        # TODO delete from body
        if tag not in self.meta.get('keywords', []):
            return
        if len(self.meta['keywords']) == 1:
            del self.meta['keywords']
        else:
            self.meta['keywords'].remove(tag)
        self.edited = True

    def _set_title(self, edit: SetTitleCmd):
        self.edited = self.edited or not self.meta.get('title') == edit.value
        self.meta['title'] = edit.value

    def _set_created(self, edit: SetCreatedCmd):
        self.edited = self.edited or not self.meta.get('created') == edit.value
        self.meta['created'] = edit.value

    def _replace_ref(self, edit: ReplaceRefCmd):
        if edit.original not in self.refs:
            return
        self.edited = True
        self.body = replace_ref(self.body, edit.original, edit.replacement)
