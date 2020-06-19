from pathlib import Path
import re
from typing import Dict, Set
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


def replace_refs(doc: str, replacements: Dict[str, str]) -> str:
    for src, dest in replacements.items():
        escaped_src = re.escape(src)
        escaped_dest = dest.replace('\\', r'\\')
        inline = rf'(\[.*\])\({escaped_src}\)'
        doc = re.sub(inline, rf'\1({escaped_dest})', doc)
        refstyle = rf'(?m)(^\[.*\]:\s*){escaped_src}(\s|$)'
        doc = re.sub(refstyle, rf'\1{escaped_dest}\2', doc)
    return doc


class MarkdownAccessor(BaseAccessor):
    def parse(self, path: Path) -> FileInfo:
        text = path.read_text()
        meta = extract_meta(text)
        return FileInfo(
            path=path,
            refs=extract_refs(text),
            tags=extract_tags(text),
            title=meta.get('title')
        )

    def change(self, path: Path, edit: FileEdit) -> bool:
        orig = path.read_text()
        changed = replace_refs(orig, edit.replace_refs)
        if not orig == changed:
            path.write_text(changed)
            return True
        return False
