#!/usr/bin/env python3
"""Render digests/*.md to HTML, rebuild index.html, commit & push.
Usage: python3 scripts/publish.py digests/2026-10-14.md [--no-push]
  (the md file may live elsewhere; it is copied into digests/YYYY-MM-DD.md)"""
import html, json, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "digests"
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEAD = re.compile(r"^- \*\*(.+?)\*\*\s*(?:\{#([\w-]+)\})?\s*(.*)$")
STORIES = {}  # id -> {title, appearances:[{date, anchor, headline}]}
CUR = {"date": None, "n": 0}
ITEM = re.compile(r"^- \[([^\]]+)\]\(([^)]+)\)[：:]\s*(.*)$")

TAG = re.compile(r"^\s*\[(长推|系列|长文)\]\s*")
SECTION_IDS = {}

def inline(t):
    out, last = [], 0
    for m in LINK.finditer(t):
        out.append(html.escape(t[last:m.start()]))
        out.append(f'<a href="{html.escape(m.group(2))}" target="_blank" rel="noopener">{html.escape(m.group(1))}</a>')
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

def src_btn(t, u):
    m = re.match(r"^(.*?)\s*@(\w+)$", t.strip())
    if m:
        name, h = m.group(1) or "@" + m.group(2), m.group(2)
        kind = "𝕏"
        label = f'<b>{html.escape(name)}</b><span class="h">@{html.escape(h)}</span>'
    else:
        kind = "↗"; label = f'<b>{html.escape(t)}</b>'
    return f'<a class="srcbtn" href="{html.escape(u)}" target="_blank" rel="noopener"><i>{kind}</i>{label}</a>'

def render_body(md):
    """returns title, overview_html, sections=[(name, sid, [item_html]), ...], heads=[(anchor, text, section)]"""
    title, overview, sections, heads, loose = "", "", [], [], []
    for line in md.splitlines():
        line = line.rstrip()
        if line.startswith("# "): title = line[2:].strip(); continue
        if line.startswith("## "):
            name = line[3:].strip(); sid = f"sec-{len(sections)+1}"
            sections.append([name, sid, []]); continue
        if line.startswith("> "):
            txt = re.sub(r"^\*\*今日要点\*\*[：:]?\s*|^今日要点[：:]\s*", "", line[2:].strip())
            overview = f'<div class="overview"><div class="ov-title">今日要点</div><p>{inline(txt)}</p></div>'; continue
        mh = HEAD.match(line)
        if mh:
            if not sections: sections.append(["其他", "sec-0", []])
            CUR["n"] += 1
            sid = mh.group(2); anchor = sid or f"item-{CUR['n']}"
            detail = mh.group(3).lstrip("：: "); badge = ""
            mt = TAG.match(detail)
            if mt:
                detail = detail[mt.end():].lstrip("：: ")
                badge = f'<span class="tag tag-{"thread" if mt.group(1)=="系列" else "long"}" title="已阅读完整版本">{mt.group(1)}</span>'
            srcs, follow, authors = "", "", []
            ms = re.search(r"\s*来源[：:]\s*(.+)$", detail)
            if ms:
                detail = detail[:ms.start()]
                links = LINK.findall(ms.group(1))
                srcs = "".join(src_btn(t, u) for t, u in links)
                for t, u in links:
                    a = re.sub(r"\s*@\w+$", "", t).strip() or t
                    if a not in authors: authors.append(a)
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
            who = f'<div class="who">{" · ".join(html.escape(a) for a in authors[:4])}{" 等" if len(authors)>4 else ""}</div>' if authors else ""
            sections[-1][2].append(
                f'<li class="item" id="{html.escape(anchor)}"><div class="headline"><a class="anchor" href="#{html.escape(anchor)}" aria-label="链接">#</a>{inline(mh.group(1))}{badge}</div>{who}'
                f'<div class="summary">{inline(detail.strip())}</div>{follow}{rel}'
                + (f'<div class="src"><span class="srcl">原文</span>{srcs}</div>' if srcs else "") + "</li>")
            heads.append((anchor, re.sub(r"\*\*", "", mh.group(1)), sections[-1][1], bool(badge)))
            continue
        m = ITEM.match(line)
        if m:
            if not sections: sections.append(["其他", "sec-0", []])
            sections[-1][2].append(f'<li class="item"><div>{author(m.group(1))}</div><div class="summary">{inline(m.group(3))}</div>'
                                   f'<div class="src">{src_btn(m.group(1), m.group(2))}</div></li>'); continue
        if line.startswith("- "):
            if sections: sections[-1][2].append(f'<li class="item">{inline(line[2:])}</li>')
            continue
        if line.strip(): loose.append(f"<p>{inline(line)}</p>")
    return title, overview, sections, heads, "".join(loose)

def compose(date, title, overview, sections, heads, loose, prefix, datenav):
    total = sum(len(s[2]) for s in sections)
    nlong = sum(1 for h in heads if h[3])
    toc = "".join(f'<li><a href="#{sid}"><span>{html.escape(n)}</span><em>{len(it)}</em></a></li>' for n, sid, it in sections)
    chips = "".join(f'<button type="button" data-sec="{sid}">{html.escape(n)} <em>{len(it)}</em></button>' for n, sid, it in sections)
    quick = []
    for n, sid, it in sections:
        hs = [h for h in heads if h[2] == sid]
        if not hs: continue
        quick.append(f'<div class="qgroup"><div class="qsec">{html.escape(n)}</div><ol>' + "".join(
            f'<li><a href="#{html.escape(a)}">{html.escape(t)}</a></li>' for a, t, _, _ in hs) + "</ol></div>")
    secs = "".join(f'<section class="sec" id="{sid}" data-sec="{sid}"><h2>{html.escape(n)}<span class="cnt">{len(it)} 条</span></h2><ul class="items">{"".join(it)}</ul></section>'
                   for n, sid, it in sections)
    stats = f'<div class="stats"><span>{total} 条</span><span>{len(sections)} 个栏目</span><span>{nlong} 条长推/系列已读全文</span></div>'
    return f"""{datenav}{stats}{overview}
<details class="quick" open><summary>今日标题速览</summary><div class="qwrap">{"".join(quick)}</div></details>
<div class="toolbar"><input id="q" type="search" placeholder="搜索标题、内容或作者…" aria-label="搜索"><div class="chips"><button type="button" data-sec="" class="on">全部 <em>{total}</em></button>{chips}</div><div id="qn" class="qn"></div></div>
<div class="layout"><aside class="toc"><div class="toc-t">目录</div><ol>{toc}</ol><a class="totop" href="#top">↑ 回到顶部</a></aside>
<div class="content">{secs}{loose}<p id="empty" class="empty" hidden>没有匹配的条目</p></div></div>"""

SCRIPT = """<script>
(function(){var d=document.querySelector('details.quick');if(d&&window.innerWidth<600)d.open=false;var q=document.getElementById('q');if(!q)return;var cur='';var items=[].slice.call(document.querySelectorAll('.item'));
var chips=[].slice.call(document.querySelectorAll('.chips button'));var n=document.getElementById('qn'),e=document.getElementById('empty');
function run(){var v=q.value.trim().toLowerCase(),c=0;items.forEach(function(li){var s=li.closest('.sec');var ok=(!cur||s.dataset.sec===cur)&&(!v||li.textContent.toLowerCase().indexOf(v)>=0);li.hidden=!ok;if(ok)c++;});
document.querySelectorAll('.sec').forEach(function(s){s.hidden=!s.querySelector('.item:not([hidden])');});n.textContent=(v||cur)?('显示 '+c+' 条'):'';e.hidden=c>0;}
q.addEventListener('input',run);chips.forEach(function(b){b.addEventListener('click',function(){cur=b.dataset.sec;chips.forEach(function(x){x.classList.toggle('on',x===b)});run();});});
var links=[].slice.call(document.querySelectorAll('.toc a[href^="#sec"]'));if('IntersectionObserver' in window){var ob=new IntersectionObserver(function(es){es.forEach(function(en){if(en.isIntersecting){links.forEach(function(a){a.classList.toggle('act',a.getAttribute('href')==='#'+en.target.id)})}})},{rootMargin:'-20% 0px -70% 0px'});document.querySelectorAll('.sec').forEach(function(s){ob.observe(s)});}
})();</script>"""

def page(title, body, css, nav, script=False):
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><title>{html.escape(title)}</title>
<link rel="stylesheet" href="{css}"></head><body id="top"><header class="top"><div class="bar"><nav>{nav}</nav></div></header><main>
<h1>{html.escape(title)}</h1>
{body}
<footer>X 每日 AI 摘要 · 由小X整理 · 每天北京时间早上更新 · 每条均附原文链接，标注「长推/系列」的已阅读完整版本</footer></main>{SCRIPT if script else ""}</body></html>
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
    out = ['<p class="note">按最近更新排序；出现超过一天的为持续事件。</p><ul class="items">']
    for sid, st in items:
        apps = st["appearances"]; tag = '<span class="tag tag-thread">持续</span>' if len(apps) > 1 else ""
        tl = "".join(f'<li><a href="digests/{a["date"]}.html#{a["anchor"]}">{a["date"]}</a> {html.escape(a["headline"])}</li>' for a in apps)
        out.append(f'<li class="item" id="{sid}"><div class="headline">{html.escape(st["title"])}{tag}</div><div class="who">{len(apps)} 天 · {apps[0]["date"]} → {apps[-1]["date"]}</div><ul class="timeline">{tl}</ul></li>')
    out.append("</ul>")
    (ROOT / "stories.html").write_text(page("事件时间线", "\n".join(out), "assets/style.css", '<a href="index.html">X 每日 AI 摘要</a><a href="stories.html">事件时间线</a>'), encoding="utf-8")

def datenav(files, i, prefix):
    newer = files[i-1].stem if i > 0 else None
    older = files[i+1].stem if i + 1 < len(files) else None
    a = lambda d, t: f'<a href="{prefix}{d}.html">{t}</a>' if d else f'<span class="dis">{t}</span>'
    return f'<div class="datenav">{a(older, "← " + (older or "前一天"))}<span class="cur">{files[i].stem}</span>{a(newer, (newer or "后一天") + " →")}</div>'

def build():
    files = sorted(D.glob("????-??-??.md"), reverse=True)
    index_stories(files); stories_page()
    for i, f in enumerate(files):
        CUR.update(date=f.stem, n=0)
        t, ov, secs, heads, loose = render_body(f.read_text(encoding="utf-8"))
        nav = f'<a href="../index.html">X 每日 AI 摘要</a><a href="../index.html#archive">往期</a><a href="../stories.html">事件时间线</a><a href="{f.stem}.md">Markdown</a>'
        body = compose(f.stem, t, ov, secs, heads, loose, "", datenav(files, i, ""))
        (D / f"{f.stem}.html").write_text(page(t or f.stem, body, "../assets/style.css", nav, True), encoding="utf-8")
    if not files: return
    CUR.update(date=files[0].stem, n=0)
    t, ov, secs, heads, loose = render_body(files[0].read_text(encoding="utf-8"))
    b = compose(files[0].stem, t, ov, secs, heads, loose, "digests/", datenav(files, 0, "digests/"))
    b = b.replace('href="../', 'href="')
    b = re.sub(r'href="(\d{4}-\d{2}-\d{2}\.html)', r'href="digests/\1', b)
    arch = "".join(f'<li><a href="digests/{f.stem}.html">{f.stem}</a>{" <span class=tag>最新</span>" if i==0 else ""}</li>' for i, f in enumerate(files))
    body = f'{b}\n<h2 id="archive" class="arch-h">往期</h2><ul class="archive">{arch}</ul>'
    (ROOT / "index.html").write_text(page(t or "X 每日 AI 摘要", body, "assets/style.css", '<a href="index.html">X 每日 AI 摘要</a><a href="#archive">往期</a><a href="stories.html">事件时间线</a>', True), encoding="utf-8")

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
