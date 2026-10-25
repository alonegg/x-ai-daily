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
POD = ROOT / "podcast"
WEEK = "一二三四五六日"

def fmt_t(sec):
    sec = int(round(sec)); h, m, x = sec // 3600, sec // 60 % 60, sec % 60
    return f"{h}:{m:02d}:{x:02d}" if h else f"{m}:{x:02d}"

def pod_info(date):
    """podcast/DATE.mp3 (+ optional DATE.json meta, DATE.md transcript) -> dict or None"""
    mp3 = POD / f"{date}.mp3"
    if not mp3.exists(): return None
    meta = {}
    if (POD / f"{date}.json").exists(): meta = json.loads((POD / f"{date}.json").read_text(encoding="utf-8"))
    if not meta.get("duration"):
        try: meta["duration"] = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)], text=True).strip())
        except Exception: meta["duration"] = 0
    meta["size"] = mp3.stat().st_size
    tx = POD / f"{date}.md"
    meta["transcript"] = tx.read_text(encoding="utf-8") if tx.exists() else ""
    return meta

def transcript_html(md):
    out, started = [], False
    for line in md.splitlines():
        line = line.strip()
        if line.startswith("## "):
            started = True
            out.append(f"<h4>{html.escape(re.sub(r'[（(][^）)]*字[）)]', '', line[3:]).strip())}</h4>"); continue
        if started and line and not line.startswith("#"): out.append(f"<p>{html.escape(line)}</p>")
    return "".join(out)

def player(date, root):
    pi = pod_info(date)
    if not pi: return ""
    src = f"{root}podcast/{date}.mp3"; dur = pi.get("duration") or 0
    mb = pi["size"] / 1e6
    groups, cur = [], None
    for c in pi.get("chapters", []):
        g = c.get("group", "")
        if not groups or groups[-1][0] != g: groups.append((g, []))
        groups[-1][1].append(c)
    ch = ""
    if groups:
        ch = f'<details class="pod-chd" open><summary>章节 <em>{len(pi.get("chapters", []))}</em></summary><div class="pod-ch">' + "".join(
            f'<div class="pod-chg"><div class="pod-chg-t">{html.escape(g)}</div>' + "".join(
                f'<button type="button" data-t="{c["t"]}"><em>{fmt_t(c["t"])}</em><span>{html.escape(c["title"])}</span></button>' for c in cs) + "</div>"
            for g, cs in groups) + "</div></details>"
    tx = f'<details class="pod-tx"><summary>文字稿</summary><div class="pod-tx-in">{transcript_html(pi["transcript"])}</div></details>' if pi["transcript"] else ""
    title = pi.get("title") or f"{int(date[5:7])} 月 {int(date[8:])} 日 AI 播报"
    desc = pi.get("desc") or "先过今日快讯，再讲重点，最后聊值得评论的话题"
    rates = "".join(f'<button type="button" data-r="{r}"{" class=on" if r == "1" else ""}>{r}×</button>' for r in ("1", "1.25", "1.5", "2"))
    return f"""<section class="pod" id="podcast" data-date="{date}" data-dur="{dur:.1f}" data-title="{html.escape(title)}">
<div class="pod-ghost" aria-hidden="true">{date[5:7]}·{date[8:]}</div>
<div class="pod-top"><span class="pod-badge">🎧 今日播报</span><span class="pod-meta">{fmt_t(dur)} · {mb:.0f} MB{" · " + html.escape(pi["voice"]) if pi.get("voice") else ""}</span></div>
<div class="pod-title">{html.escape(title)}</div><p class="pod-desc">{html.escape(desc)}</p>
<audio class="pod-audio" controls preload="none" src="{html.escape(src)}"></audio>
<div class="pod-ui" hidden><div class="pod-ctrl"><button type="button" class="pod-skip" data-s="-15" aria-label="后退 15 秒">↺15</button><button type="button" class="pod-play" aria-label="播放"><span class="i-play">▶</span><span class="i-pause">❚❚</span></button><button type="button" class="pod-skip" data-s="30" aria-label="前进 30 秒">30↻</button>
<div class="pod-bar"><input type="range" class="pod-seek" min="0" max="{dur:.0f}" step="1" value="0" aria-label="进度"><div class="pod-time"><span class="pod-cur">0:00</span><span class="pod-now"></span><span>{fmt_t(dur)}</span></div></div></div>
<div class="pod-rates"><span>倍速</span>{rates}<a class="pod-dl" href="{html.escape(src)}" download>下载 mp3</a></div></div>
{ch}{tx}</section>
<div class="pod-mini" hidden><button type="button" class="pod-play" aria-label="播放/暂停"><span class="i-play">▶</span><span class="i-pause">❚❚</span></button><a href="#podcast" class="pod-mini-t"><b>今日播报</b><span class="pod-now"></span></a><span class="pod-cur">0:00</span><button type="button" class="pod-rate1">1×</button></div>"""

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
                overview = f'<div class="overview"><div class="ov-title">今日要点 · 一分钟速览</div>{paras(txt, 150)}{upd}</div>'
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

def compose(date, title, overview, sections, heads, loose, prefix, datenav, root="../"):
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
    wd = WEEK[__import__("datetime").date.fromisoformat(date).weekday()] if date else ""
    eyebrow = f'<div class="eyebrow"><i></i>{int(date[:4])} 年 {int(date[5:7])} 月 {int(date[8:])} 日 · 星期{wd} · 小X 整理</div>' if date else ""
    return f"""{eyebrow}<!--H1--><div class="hero">{datenav}{stats}</div>{player(date, root)}{overview}
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

POD_JS = """<script>
(function(){var P=document.getElementById('podcast');if(!P)return;var A=P.querySelector('audio'),ui=P.querySelector('.pod-ui'),mini=document.querySelector('.pod-mini');
A.removeAttribute('controls');var cd=P.querySelector('.pod-chd');if(cd&&matchMedia('(max-width:600px)').matches)cd.open=false;A.hidden=true;ui.hidden=false;var D=parseFloat(P.dataset.dur)||0,key='xd-pod-'+P.dataset.date,seek=P.querySelector('.pod-seek');
function f(s){s=Math.max(0,Math.floor(s||0));var h=Math.floor(s/3600),m=Math.floor(s/60)%60,x=s%60;return (h?h+':'+(m<10?'0':''):'')+m+':'+(x<10?'0':'')+x;}
var chs=[].slice.call(P.querySelectorAll('.pod-ch button'));
function chAt(t){var c=null;chs.forEach(function(b){if(parseFloat(b.dataset.t)<=t+0.5)c=b;});return c;}
var saved=0;try{saved=parseFloat(localStorage.getItem(key))||0;}catch(e){}
if(saved>15&&saved<D-20){P.querySelector('.pod-cur').textContent=f(saved);seek.value=saved;P.classList.add('resume');P.querySelector('.pod-now').textContent='上次听到 '+f(saved);}
var pending=saved>15&&saved<D-20?saved:0;
function go(t){if(A.readyState<1){pending=t;A.preload='auto';A.load();A.play();}else{A.currentTime=t;if(A.paused)A.play();}}
A.addEventListener('loadedmetadata',function(){if(A.duration&&isFinite(A.duration)){D=A.duration;seek.max=Math.floor(D);}if(pending){A.currentTime=pending;pending=0;}});
document.querySelectorAll('.pod-play').forEach(function(b){b.addEventListener('click',function(){if(A.paused){if(pending&&A.readyState<1)A.load();A.play();}else A.pause();});});
P.querySelectorAll('.pod-skip').forEach(function(b){b.addEventListener('click',function(){var t=Math.min(D,Math.max(0,(A.readyState?A.currentTime:pending||0)+parseFloat(b.dataset.s)));go(t);});});
chs.forEach(function(b){b.addEventListener('click',function(){go(parseFloat(b.dataset.t));});});
seek.addEventListener('input',function(){P.querySelector('.pod-cur').textContent=f(seek.value);});seek.addEventListener('change',function(){go(parseFloat(seek.value));});
var rb=[].slice.call(P.querySelectorAll('.pod-rates button')),r1=mini.querySelector('.pod-rate1'),RS=['1','1.25','1.5','2'];
function rate(r){A.playbackRate=parseFloat(r);A.defaultPlaybackRate=parseFloat(r);rb.forEach(function(b){b.classList.toggle('on',b.dataset.r===r)});r1.textContent=r+'×';try{localStorage.setItem('xd-pod-rate',r)}catch(e){}}
rb.forEach(function(b){b.addEventListener('click',function(){rate(b.dataset.r)})});r1.addEventListener('click',function(){rate(RS[(RS.indexOf(String(A.playbackRate))+1)%RS.length])});
try{var sr=localStorage.getItem('xd-pod-rate');if(sr&&RS.indexOf(sr)>=0)rate(sr);}catch(e){}
A.addEventListener('ratechange',function(){});
function st(){var p=!A.paused;document.body.classList.toggle('pod-playing',p);document.querySelectorAll('.pod-play').forEach(function(b){b.classList.toggle('on',p);b.setAttribute('aria-label',p?'暂停':'播放')});vis();}
A.addEventListener('play',function(){st();A.playbackRate=parseFloat(r1.textContent)||1;});A.addEventListener('pause',st);A.addEventListener('ended',function(){st();try{localStorage.removeItem(key)}catch(e){}});
var last=0;A.addEventListener('timeupdate',function(){var t=A.currentTime;if(document.activeElement!==seek)seek.value=Math.floor(t);document.querySelectorAll('.pod-cur').forEach(function(e){e.textContent=f(t)});
var c=chAt(t);chs.forEach(function(b){b.classList.toggle('act',b===c)});var nm=c?c.querySelector('span').textContent:'';document.querySelectorAll('.pod-now').forEach(function(e){e.textContent=nm});
if(Math.abs(t-last)>5){last=t;try{localStorage.setItem(key,t)}catch(e){}}});
var inview=true;function vis(){var on=!inview&&(!A.paused||A.currentTime>0);mini.hidden=!on;document.body.classList.toggle('pod-mini-on',on);}
if('IntersectionObserver' in window){new IntersectionObserver(function(es){inview=es[0].isIntersecting;vis();},{threshold:0}).observe(P);}
if('mediaSession' in navigator){navigator.mediaSession.metadata=new MediaMetadata({title:P.dataset.title,artist:'X 每日 AI 摘要',album:'小X 播报'});
try{navigator.mediaSession.setActionHandler('seekbackward',function(){A.currentTime=Math.max(0,A.currentTime-15)});navigator.mediaSession.setActionHandler('seekforward',function(){A.currentTime=Math.min(D,A.currentTime+30)});}catch(e){}}
})();</script>"""

THEME_HEAD = """<script>(function(){try{var t=localStorage.getItem('xd-theme');if(t)document.documentElement.classList.add(t);}catch(e){}})();</script>"""
THEME_BTN = """<button type="button" class="theme" id="themebtn" aria-label="切换深浅色"><span class="sun">☀</span><span class="moon">☾</span></button>"""
THEME_JS = """<script>(function(){var b=document.getElementById('themebtn'),r=document.documentElement;if(!b)return;b.addEventListener('click',function(){var d=r.classList.contains('dark')||(!r.classList.contains('light')&&matchMedia('(prefers-color-scheme:dark)').matches);r.classList.remove('dark','light');var t=d?'light':'dark';r.classList.add(t);try{localStorage.setItem('xd-theme',t)}catch(e){}});})();</script>"""

def h1_html(title):
    m = re.match(r"^(.*?)\s*[·•]\s*(\d{4}-\d{2}-\d{2})$", title)
    if m: return f'<h1>{html.escape(m.group(1))}<span class="h1-dot"> · </span><em>{m.group(2)}</em></h1>'
    return f"<h1>{html.escape(title)}</h1>"

def page(title, body, css, nav, script=False):
    links = re.findall(r'<a href="[^"]*"[^>]*>[^<]*</a>', nav)
    brand, rest = (links[0], links[1:]) if links else ("", [])
    brand = brand.replace("<a ", '<a class="brand" ', 1).replace(">", "><i></i>", 1)
    if 'id="podcast"' in body: rest.insert(0, '<a href="#podcast" class="navpod">🎧 播客</a>')
    h1 = h1_html(title)
    body = body.replace("<!--H1-->", h1, 1) if "<!--H1-->" in body else h1 + body
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#f5f2eb" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#131211" media="(prefers-color-scheme: dark)"><title>{html.escape(title)}</title>
{THEME_HEAD}<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect x='5' y='5' width='17' height='17' rx='5' fill='%232a5db0'/%3E%3Crect x='3' y='3' width='17' height='17' rx='5' fill='%23c2410c'/%3E%3C/svg%3E"><link rel="stylesheet" href="{css}"></head><body id="top"><header class="top"><div class="bar">{brand}<nav>{"".join(rest)}</nav>{THEME_BTN}</div></header><main>
{body}
<footer>X 每日 AI 摘要 · 由小X整理 · 每天北京时间早上更新 · 每条均附原文链接，标注「长推/系列」的已阅读完整版本</footer></main>{SCRIPT if script else ""}{POD_JS if 'id="podcast"' in body else ""}{THEME_JS}</body></html>
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
        nav = f'<a href="../index.html">X 每日 AI 摘要</a><a href="../index.html#archive">往期</a><a href="../stories.html">事件时间线</a><a href="{f.stem}.md" class="navmd">Markdown</a>'
        body = compose(f.stem, t, ov, secs, heads, loose, "", datenav(files, i, ""))
        (D / f"{f.stem}.html").write_text(page(t or f.stem, body, "../assets/style.css", nav, True), encoding="utf-8")
    if not files: return
    CUR.update(date=files[0].stem, n=0)
    t, ov, secs, heads, loose = render_body(files[0].read_text(encoding="utf-8"))
    b = compose(files[0].stem, t, ov, secs, heads, loose, "digests/", datenav(files, 0, "digests/"), root="")
    b = b.replace('href="../', 'href="')
    b = re.sub(r'href="(\d{4}-\d{2}-\d{2}\.html)', r'href="digests/\1', b)
    arch = "".join(f'<li><a href="digests/{f.stem}.html"><span class="d">{f.stem}</span><span class="n">{nitems(f)} 条</span>{'<span class="podpill">▶ 播客</span>' if (POD / f"{f.stem}.mp3").exists() else ""}{" <span class=tag>最新</span>" if i==0 else ""}</a></li>' for i, f in enumerate(files))
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
