"""Escaped Markdown subset: headings, lists, quotes, code and safe links.

Raw HTML, embedded media and arbitrary URL protocols are never interpreted.
"""
import re
from html import escape
from urllib.parse import urlsplit
from django.utils.safestring import mark_safe

INLINE = re.compile(r'(`[^`\n]+`|\[[^\[\]\n]{1,500}\]\([^\s)]{1,2048}\)|\*\*[^*\n]+\*\*|\*[^*\n]+\*)')


def inline(text):
    pieces = []
    previous = 0
    for match in INLINE.finditer(text):
        pieces.append(escape(text[previous:match.start()]))
        token = match.group()
        if token.startswith('`'):
            pieces.append('<code>' + escape(token[1:-1]) + '</code>')
        elif token.startswith('['):
            label, url = token[1:].split('](', 1)
            url = url[:-1]
            try:
                parsed = urlsplit(url)
                safe = parsed.scheme.lower() in ('https', 'http', 'mailto') or (url.startswith('/') and not url.startswith('//') and '\\' not in url)
            except ValueError:
                safe = False
            if safe:
                pieces.append('<a href="' + escape(url, quote=True) + '" rel="nofollow noopener noreferrer">' + escape(label) + '</a>')
            else:
                pieces.append(escape(label))
        elif token.startswith('**'):
            pieces.append('<strong>' + escape(token[2:-2]) + '</strong>')
        else:
            pieces.append('<em>' + escape(token[1:-1]) + '</em>')
        previous = match.end()
    pieces.append(escape(text[previous:]))
    return ''.join(pieces)


def render_markdown(content):
    output = []
    paragraph = []
    code = None
    list_open = False
    headings = []
    def flush():
        if paragraph:
            output.append('<p>' + '<br>'.join(inline(line) for line in paragraph) + '</p>')
            paragraph.clear()
    for line in content.replace('\r\n', '\n').split('\n'):
        if line.startswith('```'):
            flush()
            if list_open:
                output.append('</ul>'); list_open = False
            if code is None:
                code = []
            else:
                output.append('<pre><code>' + escape('\n'.join(code)) + '</code></pre>'); code = None
            continue
        if code is not None:
            code.append(line); continue
        is_list = bool(re.match(r'^\s*[-*] ', line))
        if list_open and not is_list:
            output.append('</ul>'); list_open = False
        heading = re.match(r'^(#{1,3})\s+(.+)$', line)
        if heading:
            flush()
            level = len(heading.group(1)) + 1
            anchor = 'section-' + str(len(headings) + 1)
            headings.append({'id': anchor, 'title': heading.group(2)})
            output.append('<h%s id="%s">%s</h%s>' % (level, anchor, inline(heading.group(2)), level))
        elif is_list:
            flush()
            if not list_open:
                output.append('<ul>'); list_open = True
            output.append('<li>' + inline(re.sub(r'^\s*[-*] ', '', line)) + '</li>')
        elif line.startswith('> '):
            flush(); output.append('<blockquote>' + inline(line[2:]) + '</blockquote>')
        elif not line.strip():
            flush()
        else:
            paragraph.append(line)
    flush()
    if list_open: output.append('</ul>')
    if code is not None: output.append('<pre><code>' + escape('\n'.join(code)) + '</code></pre>')
    return mark_safe('\n'.join(output)), headings
