#!/usr/bin/env python3
"""Builds the EN/PL guides from docs/guide.<lang>.md (run by the developer, not on the Pi):

    pip install markdown playwright   # once
    python3 tools/build_guides.py

Output (committed, so the Pi needs nothing extra):
    static/guide/guide.<lang>.html                  – fragment shown in the app at /guide
    static/guide/plex-downloader-guide-<lang>.pdf   – PDF to download
"""
import html
import os
import re
import sys

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "static", "guide")
LANGS = {"en": ("Contents", "Download PDF", "Plex Downloader – guide", "Installation and user guide", "Page", "of"),
         "pl": ("Spis treści", "Pobierz PDF", "Plex Downloader – instrukcja", "Przewodnik instalacji i obsługi", "Strona", "z")}

PRINT_CSS = """
@page { size: A4; margin: 16mm 15mm 18mm 15mm; }
body { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 10pt; line-height: 1.55; color: #1d232c; }
.kicker { color: #d9820b; font-weight: 700; font-size: 8.5pt; letter-spacing: .06em; text-transform: uppercase; margin: 0 0 4pt; }
h1 { font-size: 21pt; line-height: 1.2; margin: 0 0 6pt; color: #111; }
p.lead { color: #3a6ea5; font-size: 10.5pt; margin: 0 0 10pt; padding-bottom: 10pt; border-bottom: 2pt solid #111; }
p.toc-title { font-weight: 700; margin: 14pt 0 4pt; }
h2 { font-size: 14.5pt; margin: 22pt 0 8pt; color: #111; page-break-after: avoid; display: flex; align-items: center; gap: 8pt; }
h2 .stage { background: #111; color: #fff; font-size: 8pt; font-weight: 700; letter-spacing: .05em; padding: 2pt 6pt; border-radius: 2pt; white-space: nowrap; }
h3 { font-size: 11.5pt; margin: 14pt 0 4pt; page-break-after: avoid; }
code { font-family: Menlo, Consolas, "DejaVu Sans Mono", monospace; font-size: 8.6pt; background: #f2f4f7; padding: 0 2pt; border-radius: 2pt; }
pre { background: #f6f7f9; border: 0.5pt solid #d7dce3; border-left: 2.5pt solid #9aa3af; border-radius: 3pt; padding: 7pt 9pt;
      white-space: pre-wrap; word-break: break-all; page-break-inside: avoid; margin: 6pt 0 8pt; }
pre code { background: none; padding: 0; font-size: 8.4pt; line-height: 1.45; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9pt; }
tr { page-break-inside: avoid; } thead { display: table-header-group; }
th { background: #111; color: #fff; font-weight: 700; }
th, td { border: 0.5pt solid #c9d0da; padding: 4pt 6pt; text-align: left; vertical-align: top; }
tr:nth-child(even) td { background: #fafbfc; }
blockquote { margin: 8pt 0; padding: 6pt 10pt; border-left: 3pt solid #3a6ea5; background: #f2f6fb; page-break-inside: avoid; }
blockquote.warn { border-left-color: #e0a100; background: #fff7e0; }
blockquote.tip { border-left-color: #2e9d5b; background: #eef8f1; }
blockquote p { margin: 3pt 0; } blockquote ol, blockquote ul { margin: 3pt 0; padding-left: 16pt; }
a { color: #8a5d00; text-decoration: none; }
li { margin: 2pt 0; }
.anchor { display: inline; }
"""


def _prepare(src):
    """Python-Markdown needs 4-space indents in lists and has no fenced code inside list items:
    3-space indents become 4, and an indented ``` block becomes an indented code block."""
    out, fence = [], None
    for line in src.split("\n"):
        m = re.match(r"^( +)```", line)
        if fence is None and m:
            fence = len(m.group(1))
            out.append("")
            continue
        if fence is not None:
            if line.strip() == "```":
                fence = None
                out.append("")
            else:
                out.append("        " + line[fence:])
            continue
        if re.match(r"^ {3}\S", line):
            line = " " + line
        # a new list item right after indented text would be glued to that paragraph
        if re.match(r"^(\d+\.|-) ", line) and out and out[-1].startswith(" ") and out[-1].strip():
            out.append("")
        out.append(line)
    return "\n".join(out)


def _polish(body):
    """Markdown → the guide's look: stage badges, callout boxes, the contents table, inline anchors."""
    # ## Title {#id data-stage="STAGE 1"} → <h2 id="id"><span class="stage">STAGE 1</span>Title</h2>
    def h2(m):
        attrs, text = m.group(1), m.group(2)
        i = re.search(r'id="([^"]+)"', attrs)
        st = re.search(r'data-stage="([^"]+)"', attrs)
        badge = '<span class="stage">%s</span>' % st.group(1) if st else ""
        return '<h2 id="%s">%s<span class="h2t">%s</span></h2>' % (i.group(1) if i else "", badge, text)
    body = re.sub(r"<h2([^>]*)>(.*?)</h2>", h2, body)
    # > [!WARN] / [!INFO] / [!TIP] → coloured boxes
    def bq(m):
        inner = m.group(1)
        k = re.search(r"\[!(WARN|INFO|TIP)\]\s*", inner)
        cls = k.group(1).lower() if k else "info"
        if k:
            inner = inner.replace(k.group(0), "", 1)
        return '<blockquote class="%s">%s</blockquote>' % (cls, inner)
    body = re.sub(r"<blockquote>(.*?)</blockquote>", bq, body, flags=re.S)
    # paragraph classes: "text {.lead}" → <p class="lead">text</p>
    body = re.sub(r"<p>(.*?)\s*\{\.([a-z-]+)\}</p>", r'<p class="\2">\1</p>', body)
    # the first table after the contents title is the contents table
    body = re.sub(r'(<p class="toc-title">.*?</p>\s*)<table>', r'\1<table class="toc-table">', body, count=1, flags=re.S)
    # anchors in the middle of a line, e.g. "… folders** {#wizard-disks} – …"
    body = re.sub(r"\s*\{#([a-z0-9-]+)\}", r'<span class="anchor" id="\1"></span>', body)
    return body


def convert(lang):
    src = _prepare(open(os.path.join(ROOT, "docs", "guide.%s.md" % lang), encoding="utf-8").read())
    body = _polish(markdown.markdown(src, extensions=["tables", "fenced_code", "attr_list", "sane_lists"]))
    toc = [(i, ('<span class="st">%s</span>' % re.sub(r"<[^>]+>", "", st) if st else "") + re.sub(r"<[^>]+>", "", t))
           for i, st, t in re.findall(r'<h2 id="([^"]+)">(?:<span class="stage">(.*?)</span>)?<span class="h2t">(.*?)</span></h2>', body)]
    return body, toc


def main():
    version = open(os.path.join(ROOT, "VERSION")).read().strip()
    os.makedirs(OUT, exist_ok=True)
    pdfs = []
    for lang, (contents, _dl, title, foot, page_w, of_w) in LANGS.items():
        body, toc = convert(lang)
        nav = "<nav class=\"guide-toc\"><b>%s</b><ul>%s</ul></nav>" % (
            contents, "".join('<li><a href="#%s">%s</a></li>' % (i, re.sub(r"^\d+\.\s*", "", t)) for i, t in toc))
        with open(os.path.join(OUT, "guide.%s.html" % lang), "w", encoding="utf-8") as f:
            f.write("<!-- generated by tools/build_guides.py from docs/guide.%s.md – do not edit -->\n" % lang)
            f.write(nav + "\n<article class=\"guide-body\">\n" + body + "\n</article>\n")
        doc = ("<!doctype html><html lang=\"%s\"><head><meta charset=\"utf-8\"><title>%s</title><style>%s</style></head>"
               "<body><p class=\"kicker\">Plex Downloader %s • github.com/pwmeess/plex-downloader</p>%s</body></html>") % (
            lang, html.escape(title), PRINT_CSS, version, body)
        footer = ('<div style="font-size:7.5px;color:#888;width:100%%;margin:0 15mm;display:flex;justify-content:space-between;'
                  'border-top:0.5px solid #ddd;padding-top:4px;font-family:Arial,sans-serif">'
                  '<span>Plex Downloader %s — %s</span><span>%s <span class="pageNumber"></span> %s <span class="totalPages"></span></span></div>'
                  ) % (version, foot, page_w, of_w)
        pdfs.append((lang, doc, footer))
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        kw = {"executable_path": "/usr/bin/google-chrome"} if os.path.exists("/usr/bin/google-chrome") else {}
        br = p.chromium.launch(**kw)
        page = br.new_page()
        for lang, doc, footer in pdfs:
            page.set_content(doc, wait_until="load")
            out = os.path.join(OUT, "plex-downloader-guide-%s.pdf" % lang)
            page.pdf(path=out, format="A4", print_background=True, display_header_footer=True,
                     header_template="<span></span>",
                     footer_template=footer,
                     margin={"top": "15mm", "bottom": "17mm", "left": "15mm", "right": "15mm"})
            print("ok", out, os.path.getsize(out))
        br.close()


if __name__ == "__main__":
    sys.exit(main())
