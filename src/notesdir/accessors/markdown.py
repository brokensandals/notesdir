from io import StringIO
from pathlib import Path
import re
from typing import List, Set
import yaml
from notesdir.accessors.base import BaseAccessor, FileInfo, FileEdit


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
        return FileInfo(
            path=path,
            refs=extract_refs(text),
            tags=extract_tags(text),
            title=meta.get('title'),
            created=meta.get('created')
        )

    def _change(self, edits: List[FileEdit]) -> bool:
        path = edits[0].path
        orig = path.read_text()
        changed = orig
        for edit in edits:
            if edit.ACTION == 'replace_ref':
                changed = replace_ref(changed, edit.original, edit.replacement)
            elif edit.ACTION == 'set_attr':
                meta = extract_meta(changed)
                if edit.key == 'title':
                    if edit.value is None:
                        del meta['title']
                    else:
                        meta['title'] = edit.value
                elif edit.key == 'created':
                    if edit.value is None:
                        del meta['created']
                    else:
                        meta['created'] = edit.value
                else:
                    raise NotImplementedError(f'Unsupported set_attr key {edit.key}')
                changed = set_meta(changed, meta)
            else:
                raise NotImplementedError(f'Unsupported edit action {edit.action}')
        if not orig == changed:
            path.write_text(changed)
            return True
        return False
