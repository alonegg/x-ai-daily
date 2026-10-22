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
        out.append(f'<a href="{html.escape(m.group(2))}"{"" if m.group(2).startswith("#") else " target=\"_blank\" rel=\"noopener\""}>{html.escape(m.group(1))}</a>')
        last = m.end()
    out.append(html.escape(t[last:]))
    s = "".join(out)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", s)

OPEN, CLOSE = "（(「『“[‘《", "）)」』”]’》"
LABELS = ("前情", "后续", "背景", "更新", "补充")

def sentences(t):
    """split md text at 。！？ outside brackets/links; force break before 前情：/后续："""
    out, buf, depth, i = [], "", 0, 0
    while i < len(t):
        c = t[i]
        if depth == 0 and buf.strip() and any(t.startswith(l + "：", i) or t.startswith(l + ":", i) for l in LABELS):
            out.append((buf, True)); buf = ""
        buf += c
        if c in OPEN: depth += 1
        elif c in CLOSE: depth = max(0, depth - 1)
        elif c in "。！？" and depth == 0:
            out.append((buf, False)); buf = ""
        elif c == "；" and depth == 0:
            out.append((buf, None)); buf = ""
        i += 1
    if buf.strip(): out.append((buf, False))
    return out

def vislen(t): return len(LINK.sub(lambda m: m.group(1), t))

def paras(t, target=120):
    """group sentences into readable paragraphs (content unchanged, only line breaks)"""
    ps, cur = [], ""
    for sen, hard in sentences(t.strip()):
        cur += sen
        if hard or (hard is False and vislen(cur) >= target) or (hard is None and vislen(cur) >= target * 1.6):
            ps.append(cur.strip()); cur = ""
    if cur.strip():
        if ps and vislen(cur) < 36 and not any(cur.strip().startswith(l) for l in LABELS): ps[-1] += cur.strip()
        else: ps.append(cur.strip())
    res = []
    for x in ps:
        h = inline(x)
        h = re.sub(r"^(前情|后续|背景|更新|补充)[：:]\s*", r'<b class="lbl">\1</b>', h)
        res.append(f"<p>{h}</p>")
    return "".join(res)

def author(label):
    m = re.match(r"^(.*?)\s*(@\w+)$", label.strip())
    name, h = (m.group(1), m.group(2)) if m else (label, "")
    if not name: return f'<span class="author">{html.escape(h)}</span>'
    return f'<span class="author">{html.escape(name)}</span><span class="handle">{html.escape(h)}</span>'

def platform(u, text=""):
    host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0].lower()
    if host in ("x.com", "twitter.com"): return "x", "X"
    if host.endswith("bsky.app") or host.endswith("bsky.social"): return "bsky", "Bluesky"
    if re.match(r"^https?://[^/]+/@\w", u) or any(k in host for k in ("mastodon", "hachyderm", "fosstodon", "chaos.social", "scholar.social", "mstdn")): return "masto", "Mastodon"
    if host == "github.com" or host.endswith(".github.io") and "/blob/" in u: return "gh", "GitHub"
    if host.startswith("discourse.") or "forum" in host: return "forum", "论坛"
    if any(k in host for k in ("arxiv", "biorxiv", "doi.org", "paperswithcode", "openreview", "nature.com")): return "paper", "论文"
    if any(k in host for k in ("youtube", "youtu.be", "xiaoyuzhoufm", "bilibili")): return "video", "音视频"
    if "blog" in host or "blog" in u.lower() or "substack" in host or "medium.com" in host or "博客" in text or host in ("words.yuvi.in", "chrisholdgraf.com", "daniel.haxx.se", "diff.wikimedia.org"): return "blog", "博客"
    return "web", "网页"

def src_btn(t, u):
    """kept for the legacy '- [author](url)：' item format"""
    k, lab = platform(u, t)
    m = re.match(r"^(.*?)\s*@(\w+)$", t.strip())
    name = (m.group(1) or "@" + m.group(2)) if m else t
    return f'<a class="srcbtn" href="{html.escape(u)}" target="_blank" rel="noopener"><i class="pf pf-{k}">{lab}</i><b>{html.escape(name)}</b></a>'

def src_row(links, label="原文"):
    groups = []  # [(name, handle, kind, lab, [urls])]
    for t, u in links:
        k, lab = platform(u, t)
        m = re.match(r"^(.*?)\s*@(\w+)$", t.strip())
        name, h = ((m.group(1) or "@" + m.group(2)), m.group(2)) if m else (t.strip(), "")
        for g in groups:
            if g[0] == name and g[2] == k: g[4].append(u); break
        else: groups.append((name, h, k, lab, [u]))
    chips = []
    for name, h, k, lab, us in groups:
        tip = html.escape(f"{name}{' @' + h if h else ''} · {lab}")
        pf = f'<i class="pf pf-{k}">{lab}</i>'
        if len(us) == 1:
            chips.append(f'<a class="srcbtn" href="{html.escape(us[0])}" target="_blank" rel="noopener" title="{tip}">{pf}<b>{html.escape(name)}</b></a>')
        else:
            nums = "".join(f'<a href="{html.escape(u)}" target="_blank" rel="noopener" title="{tip} · 第 {j} 条">{j}</a>' for j, u in enumerate(us, 1))
            chips.append(f'<span class="srcbtn multi" title="{tip}">{pf}<b>{html.escape(name)}</b><span class="nums">{nums}</span></span>')
    if len(chips) > 8:
        body = "".join(chips[:6]) + f'<details class="more"><summary>+{len(chips)-6} 个来源</summary><div class="more-in">{"".join(chips[6:])}</div></details>'
    else: body = "".join(chips)
    return f'<div class="src"><span class="srcl">{label} {len(links)}</span>{body}</div>'

def render_body(md):
    """returns title, overview_html, sections=[(name, sid, [item_html]), ...], heads=[(anchor, text, section, long)]"""
    title, overview, sections, heads, loose = "", "", [], [], []
    def cur_sec():
        if not sections: sections.append(["其他", "sec-0", []])
        return sections[-1][2]
    for line in md.splitlines():
        line = line.rstrip()
        if line.startswith("# "): title = line[2:].strip(); continue
        if line.startswith("## "):
            name = line[3:].strip(); sid = f"sec-{len(sections)+1}"
            sections.append([name, sid, []]); continue
        if line.startswith("### "):
            cur_sec().append(f'<li class="sub"><h3>{inline(line[4:].strip())}</h3></li>'); continue
        if line.startswith(">"):
            raw = line[1:].strip()
            if not overview and not sections:
                txt = re.sub(r"^\*\*今日要点\*\*[：:]?\s*|^今日要点[：:]\s*", "", raw)
                upd = ""
                mu = re.search(r"[（(](\d{1,2}:\d{2})\s*更新[：:]\s*(.+?)[）)]\s*$", txt)
                if mu:
                    txt = txt[:mu.start()].rstrip()
                    upd = f'<div class="upd"><b>{mu.group(1)} 更新</b>{inline(mu.group(2))}</div>'
                overview = f'<div class="overview"><div class="ov-title">今日要点</div>{paras(txt, 150)}{upd}</div>'
            else:
                cls = "callout opinion" if raw.startswith("▍") else "callout"
                cur_sec().append(f'<li class="{cls}">{inline(raw)}</li>')
            continue
        mh = HEAD.match(line)
        if mh:
            CUR["n"] += 1
            sid = mh.group(2); anchor = sid or f"item-{CUR['n']}"
            htxt = mh.group(1)
            detail = mh.group(3).lstrip("：: "); badges = []
            mt = TAG.match(detail)
            if mt:
                detail = detail[mt.end():].lstrip("：: ")
                badges.append(f'<span class="tag tag-{"thread" if mt.group(1)=="系列" else "long"}" title="已阅读完整版本">{mt.group(1)}</span>')
            srcs, follow, authors = "", "", []
            ms = re.search(r"\s*(来源|原帖)[：:]\s*(\[.+)$", detail)
            if ms:
                detail = detail[:ms.start()]
                links = LINK.findall(ms.group(2))
                srcs = src_row(links, "原文" if ms.group(1) == "来源" else "原帖")
                for t, u in links:
                    a = re.sub(r"\s*@\w+$", "", t).strip() or t
                    if a not in authors: authors.append(a)
            mf = re.search(r"\s*后续[：:]\s*(.+)$", detail)
            if mf: detail, follow = detail[:mf.start()], mf.group(1).strip()
            mfh = re.match(r"^(.{0,16}?)\s*后续[：:]\s*(.+)$", htxt)
            if mfh: htxt = (mfh.group(1) + "：" if mfh.group(1) else "") + mfh.group(2)
            prev = [a for a in STORIES.get(sid, {}).get("appearances", []) if a["date"] < CUR["date"]] if sid else []
            lk = f'<a class="prevlink" href="{prev[-1]["date"]}.html#{prev[-1]["anchor"]}">接 {prev[-1]["date"][5:]} ↩</a>' if prev else ""
            ctx, rel = "", ""
            if follow or mfh:
                badges.insert(0, '<span class="tag tag-follow">后续</span>')
            if follow:
                c = re.sub(r"^前情[：:]\s*", "", detail.strip())
                if c: ctx = f'<div class="prev"><b>前情</b>{inline(c)} {lk}</div>'
                elif lk: ctx = f'<div class="prev"><b>前情</b>{lk}</div>'
                body = follow
            else:
                body = detail
                if lk and prev: ctx = f'<div class="prev"><b>此前</b>{lk}</div>'
            if sid and sid in STORIES:
                others = [a for a in STORIES[sid]["appearances"] if a["date"] != CUR["date"]]
                if others:
                    rel = '<div class="story"><span>同一事件</span>' + "".join(f'<a href="{a["date"]}.html#{a["anchor"]}">{a["date"][5:]}</a>' for a in others) + f'<a href="../stories.html#{sid}">时间线 →</a></div>'
            who = f'<div class="who">{" · ".join(html.escape(a) for a in authors[:4])}{" 等 " + str(len(authors)) + " 位" if len(authors)>4 else ""}</div>' if authors else ""
            cur_sec().append(
                f'<li class="item" id="{html.escape(anchor)}"><div class="headline"><a class="anchor" href="#{html.escape(anchor)}" aria-label="本条链接">#</a><span class="ht">{inline(htxt)}</span>{"".join(badges)}</div>{who}'
                f'{ctx}<div class="summary">{paras(body)}</div>{rel}{srcs}</li>')
            heads.append((anchor, re.sub(r"\*\*", "", htxt), sections[-1][1], any("tag-long" in b or "tag-thread" in b for b in badges)))
            continue
        m = ITEM.match(line)
        if m:
            cur_sec().append(f'<li class="item"><div>{author(m.group(1))}</div><div class="summary">{paras(m.group(3))}</div>'
                             f'<div class="src">{src_btn(m.group(1), m.group(2))}</div></li>'); continue
        if line.startswith("- "):
            cur_sec().append(f'<li class="item plain">{paras(line[2:])}</li>'); continue
        if line.strip():
            if sections: cur_sec().append(f'<li class="para">{paras(line)}</li>')
            else: loose.append(f"<p>{inline(line)}</p>")
    return title, overview, sections, heads, "".join(loose)

def sec_class(n):
    if n.startswith("值得评论"): return " sec-pick"
    if "动向" in n or "人物" in n: return " sec-people"
    return ""

def compose(date, title, overview, sections, heads, loose, prefix, datenav):
    count = lambda it: sum(1 for x in it if x.startswith('<li class="item"'))
    total = sum(count(s[2]) for s in sections if not s[0].startswith("值得评论"))
    nlong = sum(1 for h in heads if h[3])
    toc = "".join(f'<li><a href="#{sid}"><span>{html.escape(n)}</span><em>{count(it)}</em></a></li>' for n, sid, it in sections)
    chips = "".join(f'<button type="button" data-sec="{sid}">{html.escape(re.sub(r"[（(].*?[）)]", "", n))} <em>{count(it)}</em></button>' for n, sid, it in sections)
    quick = []
    for n, sid, it in sections:
        hs = [h for h in heads if h[2] == sid]
        if not hs: continue
        quick.append(f'<div class="qgroup"><div class="qsec"><a href="#{sid}">{html.escape(n)}</a></div><ol>' + "".join(
            f'<li><a href="#{html.escape(a)}">{html.escape(t)}</a></li>' for a, t, _, _ in hs) + "</ol></div>")
    secs = "".join(f'<section class="sec{sec_class(n)}" id="{sid}" data-sec="{sid}"><h2><span>{html.escape(n)}</span><span class="cnt">{count(it)} 条</span></h2><ul class="items">{"".join(it)}</ul></section>'
                   for n, sid, it in sections)
    stats = f'<div class="stats"><span><b>{total}</b> 条</span><span><b>{len(sections)}</b> 个栏目</span><span><b>{nlong}</b> 条长推/系列已读全文</span></div>'
    return f"""<div class="hero">{datenav}{stats}</div>{overview}
<details class="quick"><summary>今日标题速览 <em>{len(heads)}</em></summary><div class="qwrap">{"".join(quick)}</div></details>
<div class="layout"><aside class="toc" id="toc"><div class="toc-t">目录</div><ol>{toc}</ol><a class="totop" href="#top">↑ 回到顶部</a></aside>
<div class="content"><div class="toolbar"><input id="q" type="search" placeholder="搜索标题、内容或作者…" aria-label="搜索"><div class="chips"><button type="button" data-sec="" class="on">全部</button>{chips}</div><div id="qn" class="qn"></div></div>
{secs}{loose}<p id="empty" class="empty" hidden>没有匹配的条目</p></div></div>
<div class="fab"><button type="button" id="tocbtn" aria-label="目录">☰ 目录</button><a href="#top" id="topbtn" aria-label="回到顶部">↑</a></div>"""

SCRIPT = """<script>
(function(){var q=document.getElementById('q');if(!q)return;var cur='';var items=[].slice.call(document.querySelectorAll('.item'));
var chips=[].slice.call(document.querySelectorAll('.chips button'));var n=document.getElementById('qn'),e=document.getElementById('empty');
function run(){var v=q.value.trim().toLowerCase(),c=0;items.forEach(function(li){var s=li.closest('.sec');var ok=(!cur||s.dataset.sec===cur)&&(!v||li.textContent.toLowerCase().indexOf(v)>=0);li.hidden=!ok;if(ok)c++;});
document.querySelectorAll('.sec').forEach(function(s){s.hidden=!s.querySelector('.item:not([hidden])');});document.querySelectorAll('.sub,.para,.callout').forEach(function(x){x.hidden=!!(v||cur)});n.textContent=(v||cur)?('显示 '+c+' 条'):'';e.hidden=c>0;}
q.addEventListener('input',run);chips.forEach(function(b){b.addEventListener('click',function(){cur=b.dataset.sec;chips.forEach(function(x){x.classList.toggle('on',x===b)});run();});});
var links=[].slice.call(document.querySelectorAll('.toc a[href^="#sec"]'));if('IntersectionObserver' in window){var ob=new IntersectionObserver(function(es){es.forEach(function(en){if(en.isIntersecting){links.forEach(function(a){a.classList.toggle('act',a.getAttribute('href')==='#'+en.target.id)})}})},{rootMargin:'-20% 0px -70% 0px'});document.querySelectorAll('.sec').forEach(function(s){ob.observe(s)});}
var toc=document.getElementById('toc'),tb=document.getElementById('tocbtn'),fab=document.querySelector('.fab');
if(tb)tb.addEventListener('click',function(ev){ev.stopPropagation();toc.classList.toggle('open');});
document.addEventListener('click',function(ev){if(toc.classList.contains('open')&&(!toc.contains(ev.target)||ev.target.closest('a')))toc.classList.remove('open');});
function sc(){fab.classList.toggle('show',window.scrollY>600);}window.addEventListener('scroll',sc,{passive:true});sc();
document.querySelectorAll('a[href^="#"]').forEach(function(a){a.addEventListener('click',function(){var t=document.getElementById(a.getAttribute('href').slice(1));if(t&&t.hidden){cur='';q.value='';chips.forEach(function(x){x.classList.toggle('on',!x.dataset.sec)});run();}});});
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

def nitems(f):
    n, pick = 0, False
    for l in f.read_text(encoding="utf-8").splitlines():
        if l.startswith("## "): pick = l[3:].startswith("值得评论")
        elif HEAD.match(l) and not pick: n += 1
    return n

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
    arch = "".join(f'<li><a href="digests/{f.stem}.html"><span class="d">{f.stem}</span><span class="n">{nitems(f)} 条</span>{" <span class=tag>最新</span>" if i==0 else ""}</a></li>' for i, f in enumerate(files))
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
