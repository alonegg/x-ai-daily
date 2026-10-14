#!/usr/bin/env python3
"""Render digests/*.md to HTML, rebuild index.html, commit & push.
Usage: python3 scripts/publish.py digests/2026-10-14.md [--no-push]
  (the md file may live elsewhere; it is copied into digests/YYYY-MM-DD.md)"""
import html, json, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "digests"
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEAD = re.compile(r"^- \*\*(.+?)\*\*\s*(?:\{#([\w-]+)\})?\s*[：:]?\s*(.*)$")
STORIES = {}  # id -> {title, appearances:[{date, anchor, headline}]}
CUR = {"date": None, "n": 0}
ITEM = re.compile(r"^- \[([^\]]+)\]\(([^)]+)\)[：:]\s*(.*)$")

def inline(t):
    out, last = [], 0
    for m in LINK.finditer(t):
        out.append(html.escape(t[last:m.start()]))
        out.append(f'<a href="{html.escape(m.group(2))}">{html.escape(m.group(1))}</a>')
        last = m.end()
    out.append(html.escape(t[last:]))
    s = "".join(out)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
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
        if line.startswith("> "):
            close(); txt = line[2:].strip()
            txt = re.sub(r"^\*\*今日要点\*\*[：:]?\s*|^今日要点[：:]\s*", "", txt)
            parts.append(f'<div class="overview"><div class="ov-title">今日要点</div><p>{inline(txt)}</p></div>'); continue
        mh = HEAD.match(line)
        if mh:
            if not inlist: parts.append('<ul class="items">'); inlist = True
            CUR["n"] += 1
            sid = mh.group(2); anchor = sid or f"item-{CUR['n']}"
            detail, srcs, follow = mh.group(3), "", ""
            ms = re.search(r"\s*来源[：:]\s*(.+)$", detail)
            if ms:
                detail = detail[:ms.start()]
                srcs = " · ".join(f'<a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(t)}</a>' for t, u in LINK.findall(ms.group(1)))
            mf = re.search(r"\s*后续[：:]\s*(.+)$", detail)
            if mf: detail, follow = detail[:mf.start()], mf.group(1).strip()
            rel = ""
            if sid and sid in STORIES:
                apps = STORIES[sid]["appearances"]
                prev = [a for a in apps if a["date"] < CUR["date"]]
                if follow:
                    lk = f' <a href="{prev[-1]["date"]}.html#{prev[-1]["anchor"]}">（接 {prev[-1]["date"]}）</a>' if prev else ""
                    follow = f'<div class="followup"><b>后续</b>{lk}：{inline(follow)}</div>'
                others = [a for a in apps if a["date"] != CUR["date"]]
                if others:
                    rel = '<div class="story">📌 同一事件：' + " · ".join(f'<a href="{a["date"]}.html#{a["anchor"]}">{a["date"]}</a>' for a in others) + f' · <a href="../stories.html#{sid}">时间线</a></div>'
            elif follow:
                follow = f'<div class="followup"><b>后续</b>：{inline(follow)}</div>'
            parts.append(f'<li id="{html.escape(anchor)}"><div class="headline"><a class="anchor" href="#{html.escape(anchor)}">#</a> {inline(mh.group(1))}</div><div class="summary">{inline(detail.strip())}</div>'
                         + follow + rel + (f'<div class="src">来源：{srcs}</div>' if srcs else "") + "</li>")
            continue
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

def index_stories(files):
    STORIES.clear()
    for f in sorted(files):
        for line in f.read_text(encoding="utf-8").splitlines():
            m = HEAD.match(line.rstrip())
            if m and m.group(2):
                st = STORIES.setdefault(m.group(2), {"title": re.sub(r"\*\*", "", m.group(1)), "appearances": []})
                st["title"] = re.sub(r"\*\*", "", m.group(1))
                st["appearances"].append({"date": f.stem, "anchor": m.group(2), "headline": st["title"]})
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "stories.json").write_text(json.dumps(STORIES, ensure_ascii=False, indent=2), encoding="utf-8")

def stories_page():
    items = sorted(STORIES.items(), key=lambda kv: (kv[1]["appearances"][-1]["date"], len(kv[1]["appearances"])), reverse=True)
    out = ['<p class="badge">按最近更新排序；出现超过一天的为持续事件。</p><ul class="items">']
    for sid, st in items:
        apps = st["appearances"]; tag = "持续 · " if len(apps) > 1 else ""
        tl = "".join(f'<li><a href="digests/{a["date"]}.html#{a["anchor"]}">{a["date"]}</a> {html.escape(a["headline"])}</li>' for a in apps)
        out.append(f'<li id="{sid}"><div class="headline">{html.escape(st["title"])}</div><div class="badge">{tag}{len(apps)} 天 · {apps[0]["date"]} → {apps[-1]["date"]}</div><ul class="timeline">{tl}</ul></li>')
    out.append("</ul>")
    (ROOT / "stories.html").write_text(page("事件时间线", "\n".join(out), "assets/style.css", '<a href="index.html">← 首页</a>'), encoding="utf-8")

def build():
    files = sorted(D.glob("????-??-??.md"), reverse=True)
    index_stories(files); stories_page()
    for f in files:
        CUR.update(date=f.stem, n=0)
        t, b = render_body(f.read_text(encoding="utf-8"))
        nav = f'<a href="../index.html">← 全部日期</a> · <a href="{f.stem}.md">Markdown</a>'
        (D / f"{f.stem}.html").write_text(page(t or f.stem, b, "../assets/style.css", nav), encoding="utf-8")
    if not files: return
    CUR.update(date=files[0].stem, n=0)
    t, b = render_body(files[0].read_text(encoding="utf-8"))
    b = b.replace('href="../', 'href="')
    b = re.sub(r'href="(\d{4}-\d{2}-\d{2}\.html)', r'href="digests/\1', b)
    arch = "\n".join(f'<li><a href="digests/{f.stem}.html">{f.stem}</a>{" <span class=badge>最新</span>" if i==0 else ""}</li>' for i, f in enumerate(files))
    body = f'<p class="badge">最新一期：<a href="digests/{files[0].stem}.html">{files[0].stem}</a></p>\n{b}\n<h2>往期</h2><ul class="archive">{arch}</ul>'
    (ROOT / "index.html").write_text(page(t or "X 每日 AI 摘要", body, "assets/style.css", 'X 每日 AI 摘要 · <a href="stories.html">事件时间线</a>'), encoding="utf-8")

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
