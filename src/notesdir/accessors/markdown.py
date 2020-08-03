import re
from io import StringIO
from typing import Set, Tuple, List

import yaml

from notesdir.accessors.base import Accessor
from notesdir.models import AddTagCmd, DelTagCmd, FileInfo, SetTitleCmd, SetCreatedCmd, ReplaceHrefCmd, LinkInfo

YAML_META_RE = re.compile(r'(?ms)(\A---\n(.*?)\n(---|\.\.\.)\s*\r?\n)?(.*)')
TAG_RE = re.compile(r'(\s|^)#([a-zA-Z][a-zA-Z\-_0-9]*)\b')
INLINE_HREF_RE = re.compile(r'\[.*?\]\((\S+?)\)')
REFSTYLE_HREF_RE = re.compile(r'(?m)^\[.*?\]:\s*(\S+)')
FENCED_CODE_RE = re.compile(r'(?ms)^\s*```.*?^\s*```')


def _extract_meta(doc) -> Tuple[dict, str]:
    meta = {}
    match = YAML_META_RE.match(doc)
    if match.groups()[1]:
        meta = yaml.safe_load(match.groups()[1])
    body = match.groups()[3]
    return meta, body


def _extract_hashtags(doc) -> Set[str]:
    return {t[1].lower() for t in TAG_RE.findall(doc)}


def _remove_hashtag(doc: str, tag: str) -> str:
    # TODO probably would be better to build a customized regex like replace_ref does
    def replace(match):
        if match.group(2).lower() == tag:
            return match.group(1)
        else:
            return match.group(0)
    return re.sub(TAG_RE, replace, doc)


def _extract_hrefs(doc) -> List[str]:
    return INLINE_HREF_RE.findall(doc) + REFSTYLE_HREF_RE.findall(doc)


def _replace_href(doc: str, src: str, dest: str) -> str:
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


def _split(doc: str) -> List[Tuple[bool, str]]:
    result = []
    prev = 0
    for match in re.finditer(FENCED_CODE_RE, doc):
        start, end = match.span()
        result.append((True, doc[prev:start]))
        result.append((False, match.group()))
        prev = end
    result.append((True, doc[prev:]))
    return result


class MarkdownAccessor(Accessor):
    """Responsible for parsing and updating Markdown files.

    Current support:

    * Metadata is stored in a YAML metadata header.
    * Tags can be stored in both the ``keywords`` YAML key and as hashtags in the body.
        * When this class needs to add a new tag, it will always do so in the YAML metadata.
        * When removing a tag, this class will delete any occurrences of the hashtag from the body, in addition
          to deleting from the YAML metadata.
        * Hashtags are only recognized when they are preceded by whitespace or begin the line. Hashtags must
          begin with a letter a-z and can only contain letters a-z and digits.
    * Links can be recognized and updated when they are in one of the following three formats:
        * ``[any link text](HREF)``
        * ``![any image title](HREF)``
        * (at beginning of a line) ``[any id]: HREF optional text``

    Currently, parsing and updating is done via regex, so formatting changes should be minimal but false positives
    for links and hashtags are a risk.

    Here's an example Markdown file with metadata and hashtags:

    .. code-block:: markdown

       ---
       title: My Boring Note
       created: 2001-02-03 04:05:06
       keywords:
       - boring
       - unnecessary
       ...
       The three dots indicate the end of the metadata. Now we're in **Markdown**!
       This is a really #uninteresting note.
    """
    def _load(self):
        with open(self.path, 'r') as file:
            text = file.read()
        self.meta, body = _extract_meta(text)
        self.parts = _split(body)
        self.hrefs = []
        self._hashtags = set()
        for parsable, part in self.parts:
            if parsable:
                self.hrefs.extend(_extract_hrefs(part))
                self._hashtags.update(_extract_hashtags(part))

    def _info(self, info: FileInfo):
        info.title = self.meta.get('title')
        info.created = self.meta.get('created')
        info.tags = {k.lower() for k in self.meta.get('keywords', [])}.union(self._hashtags)
        info.links = [LinkInfo(self.path, r) for r in sorted(self.hrefs)]

    def _save(self):
        body = ''.join(part for _, part in self.parts)
        if self.meta:
            sio = StringIO()
            yaml.safe_dump(self.meta, sio)
            text = f'---\n{sio.getvalue()}...\n{body}'
        else:
            text = body
        with open(self.path, 'w') as file:
            file.write(text)

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
        if tag in self.meta.get('keywords', []):
            if len(self.meta['keywords']) == 1:
                del self.meta['keywords']
            else:
                self.meta['keywords'].remove(tag)
            self.edited = True
        if tag in self._hashtags:
            for i in range(len(self.parts)):
                parsable, part = self.parts[i]
                if parsable:
                    self.parts[i] = (True, _remove_hashtag(part, tag))
            self._hashtags.remove(tag)
            self.edited = True

    def _set_title(self, edit: SetTitleCmd):
        self.edited = self.edited or not self.meta.get('title') == edit.value
        self.meta['title'] = edit.value

    def _set_created(self, edit: SetCreatedCmd):
        self.edited = self.edited or not self.meta.get('created') == edit.value
        self.meta['created'] = edit.value

    def _replace_href(self, edit: ReplaceHrefCmd):
        if edit.original not in self.hrefs:
            return
        self.edited = True
        for i in range(len(self.parts)):
            parsable, part = self.parts[i]
            if parsable:
                self.parts[i] = (True, _replace_href(part, edit.original, edit.replacement))
