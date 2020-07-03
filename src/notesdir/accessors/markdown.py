from io import StringIO
from pathlib import Path
import re
from typing import List, Set
import yaml
from notesdir.accessors.base import BaseAccessor
from notesdir.models import FileInfo, FileEditCmd, SetTitleCmd, SetCreatedCmd, ReplaceRefCmd

YAML_META_RE = re.compile(r'(?ms)\A---\n(.*)\n(---|\.\.\.)\s*$')
TAG_RE = re.compile(r'(?:\s|^)#([a-zA-Z][a-zA-Z\-_0-9]*)\b')
INLINE_REF_RE = re.compile(r'\[.*\]\((\S+)\)')
REFSTYLE_REF_RE = re.compile(r'(?m)^\[.*\]:\s*(\S+)')


def extract_meta(doc) -> dict:
    match = YAML_META_RE.match(doc)
    if not match:
        return {}
    return yaml.safe_load(match.groups()[0])


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


def set_meta(doc: str, meta: dict) -> str:
    sio = StringIO()
    yaml.safe_dump(meta, sio)
    yaml_str = sio.getvalue().rstrip('\n')
    match = YAML_META_RE.match(doc)
    if match:
        return f'{doc[:match.start(1)]}{yaml_str}{doc[match.end(1):]}'
    else:
        return f'---\n{yaml_str}\n...\n{doc}'


class MarkdownAccessor(BaseAccessor):
    def parse(self, path: Path) -> FileInfo:
        text = path.read_text()
        meta = extract_meta(text)
        info = FileInfo(path)
        info.refs = extract_refs(text)
        info.managed_tags = {k.lower() for k in meta.get('keywords', [])}
        info.unmanaged_tags = extract_tags(text)
        info.title = meta.get('title')
        info.created = meta.get('created')
        return info

    def _change(self, edits: List[FileEditCmd]) -> bool:
        path = edits[0].path
        orig = path.read_text()
        changed = orig
        for edit in edits:
            if isinstance(edit, ReplaceRefCmd):
                changed = replace_ref(changed, edit.original, edit.replacement)
            elif isinstance(edit, SetTitleCmd):
                meta = extract_meta(changed)
                if edit.value is None:
                    del meta['title']
                else:
                    meta['title'] = edit.value
                changed = set_meta(changed, meta)
            elif isinstance(edit, SetCreatedCmd):
                meta = extract_meta(changed)
                if edit.value is None:
                    del meta['created']
                else:
                    meta['created'] = edit.value
                changed = set_meta(changed, meta)
            else:
                raise NotImplementedError(f'Unsupported edit {edit}')
        if not orig == changed:
            path.write_text(changed)
            return True
        return False
