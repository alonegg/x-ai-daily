#!/usr/bin/env python3
"""Render digests/*.md to HTML, rebuild index.html, commit & push.
Usage: python3 scripts/publish.py digests/2026-10-14.md [--no-push]
  (the md file may live elsewhere; it is copied into digests/YYYY-MM-DD.md)"""
import html, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "digests"
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
ITEM = re.compile(r"^- \[([^\]]+)\]\(([^)]+)\)[：:]\s*(.*)$")

def inline(t):
    out, last = [], 0
    for m in LINK.finditer(t):
        out.append(html.escape(t[last:m.start()]))
        out.append(f'<a href="{html.escape(m.group(2))}">{html.escape(m.group(1))}</a>')
        last = m.end()
    out.append(html.escape(t[last:]))
    s = "".join(out)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", s)

def author(label):
    m = re.match(r"^(.*?)\s*(@\w+)$", label.strip())
    name, h = (m.group(1), m.group(2)) if m else (label, "")
    if not name: return f'<span class="author">{html.escape(h)}</span>'
    return f'<span class="author">{html.escape(name)}</span><span class="handle">{html.escape(h)}</span>'

def render_body(md):
    title, parts, inlist = "", [], False
    def close():
        nonlocal inlist
        if inlist: parts.append("</ul>"); inlist = False
    for line in md.splitlines():
        line = line.rstrip()
        if line.startswith("# "): title = line[2:].strip(); continue
        if line.startswith("## "):
            close(); parts.append(f"<h2>{html.escape(line[3:].strip())}</h2>"); continue
        m = ITEM.match(line)
        if m or line.startswith("- "):
            if not inlist: parts.append('<ul class="items">'); inlist = True
            if m:
                parts.append(f'<li><div>{author(m.group(1))}</div><div class="summary">{inline(m.group(3))}</div>'
                             f'<div class="src"><a href="{html.escape(m.group(2))}" target="_blank" rel="noopener">查看原帖 →</a></div></li>')
            else: parts.append(f"<li>{inline(line[2:])}</li>")
            continue
        if line.strip(): close(); parts.append(f"<p>{inline(line)}</p>")
    close()
    return title, "\n".join(parts)

def page(title, body, css, nav):
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<link rel="stylesheet" href="{css}"></head><body><main>
<nav>{nav}</nav><h1>{html.escape(title)}</h1>
{body}
<footer>X 每日 AI 摘要 · 由小X整理 · 每天北京时间早上更新</footer></main></body></html>
"""

def build():
    files = sorted(D.glob("????-??-??.md"), reverse=True)
    for f in files:
        t, b = render_body(f.read_text(encoding="utf-8"))
        nav = f'<a href="../index.html">← 全部日期</a> · <a href="{f.stem}.md">Markdown</a>'
        (D / f"{f.stem}.html").write_text(page(t or f.stem, b, "../assets/style.css", nav), encoding="utf-8")
    if not files: return
    t, b = render_body(files[0].read_text(encoding="utf-8"))
    b = b.replace('href="../', 'href="')
    arch = "\n".join(f'<li><a href="digests/{f.stem}.html">{f.stem}</a>{" <span class=badge>最新</span>" if i==0 else ""}</li>' for i, f in enumerate(files))
    body = f'<p class="badge">最新一期：<a href="digests/{files[0].stem}.html">{files[0].stem}</a></p>\n{b}\n<h2>往期</h2><ul class="archive">{arch}</ul>'
    (ROOT / "index.html").write_text(page(t or "X 每日 AI 摘要", body, "assets/style.css", "X 每日 AI 摘要"), encoding="utf-8")

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    date = None
    if a:
        src = Path(a[0]).resolve()
        m = re.search(r"(\d{4}-\d{2}-\d{2})", src.name)
        if not m: sys.exit("filename must contain YYYY-MM-DD")
        date = m.group(1); dst = D / f"{date}.md"
        if src != dst: D.mkdir(exist_ok=True); shutil.copy(src, dst)
    build()
    if "--no-push" in sys.argv: return
    g = lambda *c: subprocess.run(["git", "-C", str(ROOT), *c], check=True)
    g("add", "-A")
    if subprocess.run(["git", "-C", str(ROOT), "diff", "--cached", "--quiet"]).returncode == 0:
        print("nothing to commit"); return
    g("commit", "-m", f"digest {date or 'rebuild'}"); g("push", "origin", "HEAD:main")

if __name__ == "__main__": main()
