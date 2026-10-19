#!/usr/bin/env python3
"""一霁千山 · 书籍版生成器

读取仓库里的 Markdown 书稿，排版成一本可以在网页上阅读的书。

  python scripts/build.py --out _site
  python scripts/build.py --markdown "book/Notes to Ascence.md" --out _site
  python scripts/build.py --tree book.json --out _site  # 从本地 JSON 读取（调试用）
"""
import argparse
import base64
import datetime
import hashlib
import html
import json
import math
import os
import re
import shutil
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from fonts import build_fonts  # noqa: E402

TZ = datetime.timezone(datetime.timedelta(hours=8))
LABEL_RE = re.compile(r"^(第[^\s　]{1,6}[章节部篇卷回]|序|序言|自序|前言|引言|楔子|尾声|后记|跋|结语|附录)$")
PRINCIPLE_RE = re.compile(r"^\s*(\d{1,2})\s*[｜|丨]\s*(.+)$")


def esc(s):
    return html.escape(s or "", quote=True)


def plain(rich):
    return "".join(r.get("plain_text", "") for r in (rich or []))


def is_latin(text):
    t = re.sub(r"\s", "", text)
    if not t:
        return False
    latin = len(re.findall(r"[A-Za-z]", t))
    cjk = len(re.findall(r"[\u3400-\u9fff]", t))
    return cjk == 0 and latin / len(t) > 0.5


def reading_minutes(text):
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    words = len(re.findall(r"[A-Za-z]+", text))
    return max(1, math.ceil(cjk / 420 + words / 220))


def cn_date(dt):
    return f"{dt.year} 年 {dt.month} 月 {dt.day} 日"


class Ctx:
    def __init__(self, out_dir, links, epigraph=""):
        self.out = out_dir
        self.links = links  # notion 页面 id（无横线）→ 本站链接
        self.epigraph = epigraph
        self.all_text = []
        self.bold_text = []
        self.sections = []
        self.plain = []
        self.latest = ""

    def text(self, s, bold=False):
        self.all_text.append(s)
        if bold:
            self.bold_text.append(s)

    def seen(self, b):
        t = b.get("last_edited_time") or ""
        if t > self.latest:
            self.latest = t

    def image(self, url, key):
        if not url:
            return None
        os.makedirs(os.path.join(self.out, "img"), exist_ok=True)
        name = hashlib.sha1(key.encode()).hexdigest()[:12]
        dest = os.path.join(self.out, "img", name + ".jpg")
        try:
            if os.path.exists(url):
                data = open(url, "rb").read()
            else:
                req = urllib.request.Request(url, headers={"User-Agent": "ascence-book"})
                data = urllib.request.urlopen(req, timeout=60).read()
        except Exception as e:
            print(f"· 图片下载失败：{e}")
            return None
        try:
            from io import BytesIO
            from PIL import Image
            im = Image.open(BytesIO(data))
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (251, 250, 247))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            im = im.convert("RGB")
            im.thumbnail((1800, 1800))
            im.save(dest, "JPEG", quality=84, optimize=True, progressive=True)
        except Exception:
            open(dest, "wb").write(data)
        return "img/" + name + ".jpg"


# ---------------------------------------------------------------- 行内文字

COLOR_CLASS = {"gray": "muted", "brown": "muted"}


def rich(rt, ctx, force_bold=False):
    out = []
    for r in rt or []:
        t = r.get("plain_text", "")
        if not t:
            continue
        a = r.get("annotations") or {}
        bold = force_bold or a.get("bold")
        ctx.text(t, bold=bold)
        s = esc(t).replace("\n", "<br>")
        if a.get("code"):
            s = f"<code>{s}</code>"
        if a.get("bold") and not force_bold:
            s = f"<strong>{s}</strong>"
        if a.get("italic"):
            s = f"<em>{s}</em>"
        if a.get("strikethrough"):
            s = f"<s>{s}</s>"
        if a.get("underline"):
            s = f"<u>{s}</u>"
        color = a.get("color") or "default"
        if color != "default":
            if color.endswith("_background"):
                s = f'<mark>{s}</mark>'
            else:
                s = f'<span class="{COLOR_CLASS.get(color, "tint")}">{s}</span>'
        href = r.get("href")
        if href:
            m = re.search(r"([0-9a-f]{32})", href.replace("-", ""))
            if m and m.group(1) in ctx.links:
                s = f'<a href="{ctx.links[m.group(1)]}">{s}</a>'
            elif not re.search(r"notion\.(so|site|com)", href):
                s = f'<a href="{esc(href)}" rel="noopener">{s}</a>'
        out.append(s)
    return "".join(out)


# ---------------------------------------------------------------- 块

def render_blocks(blocks, ctx, kind, depth=0):
    html_out, i = [], 0
    blocks = blocks or []
    while i < len(blocks):
        b = blocks[i]
        t = b.get("type")
        if t in ("bulleted_list_item", "numbered_list_item", "to_do"):
            tag = "ol" if t == "numbered_list_item" else "ul"
            items = []
            while i < len(blocks) and blocks[i].get("type") == t:
                items.append(render_li(blocks[i], ctx, kind, depth))
                i += 1
            html_out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        html_out.append(render_block(b, ctx, kind, depth))
        i += 1
    return "\n".join(h for h in html_out if h)


def render_li(b, ctx, kind, depth):
    ctx.seen(b)
    t = b["type"]
    body = rich(b[t].get("rich_text"), ctx)
    ctx.plain.append(plain(b[t].get("rich_text")))
    if t == "to_do":
        body = ("☑ " if b[t].get("checked") else "☐ ") + body
    kids = render_blocks(b.get("children"), ctx, kind, depth + 1)
    return f"<li>{body}{kids}</li>"


def render_block(b, ctx, kind, depth):
    ctx.seen(b)
    t = b.get("type")
    d = b.get(t) or {}
    rt = d.get("rich_text")
    txt = plain(rt).strip()
    kids = lambda: render_blocks(b.get("children"), ctx, kind, depth + 1)  # noqa: E731
    if rt is not None:
        ctx.plain.append(txt)

    if t == "paragraph":
        if not txt:
            return ""
        runs = [r for r in rt if r.get("plain_text", "").strip()]
        all_bold = bool(runs) and all((r.get("annotations") or {}).get("bold") for r in runs)
        if all_bold and is_latin(txt):
            ctx.text(txt)
            return f'<p class="en">{esc(txt)}</p>' + kids()
        if all_bold:
            return f'<p class="lead">{rich(rt, ctx)}</p>' + kids()
        cls = ""
        if ctx.epigraph and txt == ctx.epigraph:
            cls = ' class="verse"'
        return f"<p{cls}>{rich(rt, ctx)}</p>" + kids()

    if t in ("heading_1", "heading_2"):
        if not txt:
            return ""
        ctx.sections.append(txt)
        sid = f"s{len(ctx.sections)}"
        return f'<h2 id="{sid}">{rich(rt, ctx, force_bold=True)}</h2>' + kids()

    if t == "heading_3":
        if not txt:
            return ""
        m = PRINCIPLE_RE.match(txt)
        if m:
            ctx.text(m.group(1))
            ctx.text(m.group(2), bold=True)
            return (f'<h3 class="pr"><span class="no">{esc(m.group(1))}</span>'
                    f'<span class="pt">{esc(m.group(2))}</span></h3>') + kids()
        return f"<h3>{rich(rt, ctx, force_bold=True)}</h3>" + kids()

    if t == "quote":
        inner = rich(rt, ctx)
        return f"<blockquote><p>{inner}</p>{kids()}</blockquote>" if (inner or b.get("children")) else ""

    if t == "callout":
        return f'<aside class="note"><p>{rich(rt, ctx)}</p>{kids()}</aside>'

    if t == "divider":
        return '<div class="orn" aria-hidden="true">·　·　·</div>'

    if t == "image":
        src = (d.get(d.get("type", "")) or {}).get("url")
        url = ctx.image(src, b.get("id", src or ""))
        if not url:
            return ""
        cap = rich(d.get("caption"), ctx)
        capt = f"<figcaption>{cap}</figcaption>" if cap else ""
        return f'<figure><img src="{url}" alt="{esc(plain(d.get("caption")))}" loading="lazy">{capt}</figure>'

    if t == "toggle":
        return (f"<p>{rich(rt, ctx)}</p>" if txt else "") + kids()

    if t in ("column_list", "column", "synced_block"):
        return kids()

    if t == "code":
        return f"<pre><code>{esc(txt)}</code></pre>"

    if t == "equation":
        e = d.get("expression", "")
        ctx.text(e)
        return f'<p class="eq">{esc(e)}</p>'

    if t in ("bookmark", "embed", "link_preview", "video", "file", "pdf"):
        url = d.get("url") or (d.get(d.get("type", "")) or {}).get("url")
        if not url or "amazonaws" in url:
            return ""
        cap = plain(d.get("caption")) or url
        ctx.text(cap)
        return f'<p class="link"><a href="{esc(url)}" rel="noopener">{esc(cap)}</a></p>'

    if t == "table":
        rows = []
        for r in b.get("children") or []:
            cells = (r.get("table_row") or {}).get("cells") or []
            rows.append("<tr>" + "".join(f"<td>{rich(c, ctx)}</td>" for c in cells) + "</tr>")
        return '<table>' + "".join(rows) + "</table>"

    return ""  # table_of_contents、breadcrumb、child_page 等不进入正文


# ---------------------------------------------------------------- 结构

def split_title(title, group):
    title = title.strip()
    m = re.match(r"^(\S+?)[\s　]+(.+)$", title)
    if m and LABEL_RE.match(m.group(1)):
        return m.group(1), m.group(2).strip()
    if LABEL_RE.match(title):
        return title, ""
    if group:
        return group, title
    return "", title


def parse_root(book):
    info = {"title": book.get("title") or "一霁千山", "subtitle": "", "epigraph": "",
            "footer": "", "author": "", "intro": [], "chapters": []}
    group, seen_page, pending = None, False, []
    cur = None  # 正文直接写在主页面里：每个一级标题是一章，分隔线结束正文
    for b in book.get("blocks", []):
        t = b.get("type")
        if t == "heading_1":
            title = plain(b[t]["rich_text"]).strip()
            if title:
                if seen_page and pending and cur is None:
                    group = pending[-1]
                pending = []
                seen_page = True
                cur = {"id": b["id"], "title": title, "blocks": []}
                info["chapters"].append({"page": cur, "group": group, "id": b["id"]})
            continue
        if cur is not None:
            if t == "divider":
                cur = None
            elif t != "child_page":
                cur["blocks"].append(b)
                continue
            else:
                cur = None
        if t == "child_page" and b.get("page"):
            if seen_page and pending:
                group = pending[-1]
            pending = []
            seen_page = True
            info["chapters"].append({"page": b["page"], "group": group, "id": b["id"]})
        elif t == "quote" and not seen_page and not info["epigraph"]:
            info["epigraph"] = plain(b["quote"]["rich_text"]).strip()
        elif t in ("paragraph", "heading_1", "heading_2", "heading_3"):
            txt = plain(b[t]["rich_text"]).strip()
            if not txt:
                continue
            if not seen_page:
                if not info["subtitle"]:
                    info["subtitle"] = txt
                elif not info["author"]:
                    info["author"] = txt
                else:
                    info["intro"].append(txt)
            else:
                pending.append(txt)
    if pending:
        info["footer"] = pending[-1]
    counters = {}
    for ch in info["chapters"]:
        label, name = split_title(ch["page"].get("title", ""), ch["group"])
        if label in ("尾声", "后记", "跋", "结语"):
            kind = "coda"
        elif label in ("序", "序言", "自序", "前言", "引言", "楔子"):
            kind = "preface"
        elif label == "附录" or ch["group"]:
            kind = "appendix"
        else:
            kind = "chapter"
        base = {"coda": "coda", "preface": "preface", "appendix": "appendix", "chapter": "chapter"}[kind]
        counters[base] = counters.get(base, 0) + 1
        n = counters[base]
        slug = f"{base}-{n}" if base in ("chapter", "appendix") or n > 1 else base
        ch.update(label=label, name=name, kind=kind, slug=slug + ".html")
    return info


# ---------------------------------------------------------------- 页面

AUTHOR = ""


def head(title, desc, css_href, fonts_preload, theme_color="#FBFAF7", og_image=""):
    pre = "".join(
        f'<link rel="preload" href="{f}" as="font" type="font/{f.rsplit(".", 1)[1]}" crossorigin>'
        for f in fonts_preload)
    og = f'<meta property="og:image" content="{og_image}">' if og_image else ""
    return f"""<!doctype html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{f'<meta name="author" content="{esc(AUTHOR)}">' if AUTHOR else ''}
<meta name="theme-color" content="{theme_color}">
<meta property="og:type" content="book">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
{og}
<link rel="icon" href="favicon.svg" type="image/svg+xml">
{pre}
<link rel="stylesheet" href="{css_href}">
<script>(function(){{var d=document.documentElement;d.className+=' js';try{{var t=localStorage.getItem('as-theme'),s=localStorage.getItem('as-size');if(t)d.setAttribute('data-theme',t);if(s)d.setAttribute('data-size',s);}}catch(e){{}}}})();</script>
</head>
"""


PANEL = """<div class="panel" role="dialog" aria-label="阅读设置" hidden>
<div class="row"><span>字号</span><button type="button" data-size="-1" aria-label="缩小字号">A<small>－</small></button><button type="button" data-size="1" aria-label="放大字号">A<small>＋</small></button></div>
<div class="row"><span>底色</span><button type="button" data-theme="paper">纸</button><button type="button" data-theme="night">夜</button></div>
</div>"""


def author_name(info):
    return (info.get("author") or "").strip()


def colophon(info):
    a = f'<div>{esc(info["author"])}</div>' if info.get("author") else ""
    return (f'<footer class="colophon"><div>{esc(info["title"])}</div>{a}'
            f'<div class="en">{esc(info["subtitle"])}</div></footer>')


def write(path, s):
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)


def build(book, out, font_src=None, site_url=""):
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    global AUTHOR
    info = parse_root(book)
    AUTHOR = author_name(info)
    chapters = info["chapters"]
    links = {ch["id"].replace("-", ""): ch["slug"] for ch in chapters}
    for ch in chapters:
        links[ch["page"]["id"].replace("-", "")] = ch["slug"]

    all_text, bold_text = [], []
    latest = book.get("last_edited_time") or ""

    # 正文
    for ch in chapters:
        ctx = Ctx(out, links, info["epigraph"])
        ch["html"] = render_blocks(ch["page"].get("blocks"), ctx, ch["kind"])
        ch["sections"] = ctx.sections
        ch["minutes"] = reading_minutes(" ".join(ctx.plain))
        all_text += ctx.all_text
        bold_text += ctx.bold_text
        latest = max(latest, ctx.latest)

    try:
        updated = datetime.datetime.fromisoformat(latest.replace("Z", "+00:00")).astimezone(TZ)
    except Exception:
        updated = datetime.datetime.now(TZ)

    title, subtitle, epi = info["title"], info["subtitle"], info["epigraph"]
    foot = info["footer"]
    foot_main, foot_status = (foot.split("·", 1) + [""])[:2] if "·" in foot else (foot, "")
    foot_main, foot_status = foot_main.strip(" 　"), foot_status.strip(" 　")
    if not foot_status:  # 页脚只写了状态（如「持续书写中」）
        foot_main, foot_status = "", foot_main

    # 首页 / 目录里会出现的文字也要进字体
    shell_text = [title, subtitle, epi, foot, info["author"], cn_date(updated), "目录目　录开始阅读继续阅读分钟上一章下一章回到目录最后更新于字号底色纸夜阅读设置附录此页不存在回到封面翻开"]
    for ch in chapters:
        shell_text += [ch["label"], ch["name"], ch["page"].get("title", "")] + ch["sections"]
    all_text += shell_text
    bold_text += []

    # 字体与样式
    font_css = build_fonts(font_src, os.path.join(out, "fonts"), "".join(all_text), "".join(bold_text))
    css = font_css + "\n" + open(os.path.join(ROOT, "theme", "style.css"), encoding="utf-8").read()
    ver = hashlib.sha1(css.encode()).hexdigest()[:8]
    write(os.path.join(out, "style.css"), css)
    shutil.copy(os.path.join(ROOT, "theme", "reader.js"), os.path.join(out, "reader.js"))
    shutil.copy(os.path.join(ROOT, "theme", "favicon.svg"), os.path.join(out, "favicon.svg"))
    archive_src = os.path.join(ROOT, "founder")
    if os.path.isdir(archive_src):
        shutil.copytree(archive_src, os.path.join(out, "archive"), dirs_exist_ok=True)
    preload = [f"fonts/{f}" for f in sorted(os.listdir(os.path.join(out, "fonts")))
               if f.startswith("serif-400")] if os.path.isdir(os.path.join(out, "fonts")) else []
    css_href = f"style.css?v={ver}"

    # 封面图
    cover = os.path.join(ROOT, "assets", "cover.jpg")
    b64 = cover + ".b64"
    if os.path.exists(cover):
        shutil.copy(cover, os.path.join(out, "cover.jpg"))
    elif os.path.exists(b64):
        with open(os.path.join(out, "cover.jpg"), "wb") as f:
            f.write(base64.b64decode(open(b64).read()))
    og = ""
    try:
        from PIL import Image
        im = Image.open(os.path.join(out, "cover.jpg")).convert("RGB")
        w, h = im.size
        ch_h = int(w * 630 / 1200)
        top = int(h * 0.52)
        top = min(top, h - ch_h)
        im.crop((0, top, w, top + ch_h)).resize((1200, 630)).save(os.path.join(out, "og.jpg"), "JPEG", quality=84)
        og = (site_url.rstrip("/") + "/og.jpg") if site_url else "og.jpg"
    except Exception:
        pass

    desc = epi or subtitle
    verse = "".join(f"<span>{esc(x)}</span>" for x in re.findall(r"[^，。；！？、]+[，。；！？、]?", epi)) if epi else ""

    # 目录
    toc, cur_group = [], None
    for ch in chapters:
        if ch["kind"] == "appendix" and ch["group"] != cur_group:
            cur_group = ch["group"]
            toc.append(f'<div class="toc-group">{esc(cur_group)}</div>')
        lab = "" if ch["kind"] == "appendix" else (ch["label"] if ch["name"] else "")
        tt = ch["name"] or ch["label"] or ch["page"].get("title", "")
        toc.append(
            f'<a class="l1" href="{ch["slug"]}"><span class="lab">{esc(lab)}</span>'
            f'<span class="tt">{esc(tt)}</span><span class="dots"></span>'
            f'<span class="pn">{ch["minutes"]} 分钟</span></a>')
        if ch["kind"] != "appendix" and len(ch["sections"]) > 1:
            subs = "".join(f'<a class="l2" href="{ch["slug"]}#s{i + 1}">{esc(s)}</a>'
                           for i, s in enumerate(ch["sections"]))
            toc.append(f'<div class="subs">{subs}</div>')

    first = chapters[0]["slug"] if chapters else "#toc"
    first_name = (chapters[0]["name"] or chapters[0]["label"] or chapters[0]["page"].get("title", "")) if chapters else ""
    status = foot_status or ""
    y_line = "　·　".join(x for x in [status, f"最后更新于 {cn_date(updated)}"] if x)
    home = head(f"{title} · {subtitle}" if subtitle else title, desc, css_href, preload, og_image=og) + f"""<body class="home">
<section class="cover-screen">
  <a class="book" href="#title" aria-label="翻开 {esc(title)}">
    <span class="book-t"><span class="book-h">{esc(title)}</span><span class="book-en">{esc(subtitle.upper())}</span></span>
    {f'<span class="book-b">{esc(info["author"])}</span>' if info["author"] else ''}
  </a>
  <div class="begin"><a class="go" href="#title">翻开</a></div>
  <a class="resume" href="#" hidden>接着上次读<span></span></a>
</section>
<section class="title-screen reveal" id="title">
  <h1>{esc(title)}</h1>
  <div class="en">{esc(subtitle)}</div>
  <div class="rule"></div>
  {f'<div class="a">{esc(info["author"])}</div>' if info["author"] else ''}
  <div class="y">{esc(y_line)}</div>
</section>
<section class="epi-screen reveal" aria-label="题诗"><p class="verse-v">{verse}</p></section>
<section class="toc-screen reveal" id="toc"><h2>目录</h2><nav class="toc">
{chr(10).join(toc)}
</nav>
<nav class="turn"><a class="next" href="{first}" rel="next"><small>开始阅读</small><span>{esc(first_name)}</span></a></nav>
</section>
{colophon(info)}
<script src="reader.js" defer></script>
</body>
</html>
"""
    write(os.path.join(out, "index.html"), home)

    # 章节页
    for i, ch in enumerate(chapters):
        prev = chapters[i - 1] if i > 0 else None
        nxt = chapters[i + 1] if i + 1 < len(chapters) else None

        def short(c):
            return "　".join(x for x in [c["label"], c["name"]] if x) or c["page"].get("title", "")

        turn = '<nav class="turn">'
        if prev:
            turn += f'<a class="prev" href="{prev["slug"]}" rel="prev"><small>上一页</small><span>{esc(short(prev))}</span></a>'
        else:
            turn += '<a class="prev" href="index.html#toc" rel="prev"><small>上一页</small><span>目录</span></a>'
        if nxt:
            turn += f'<a class="next" href="{nxt["slug"]}" rel="next"><small>下一页</small><span>{esc(short(nxt))}</span></a>'
        else:
            turn += '<a class="next" href="index.html" rel="next"><small>读完了</small><span>合上书</span></a>'
        turn += "</nav>"
        if ch["name"]:
            opener = f'<div class="clabel">{esc(ch["label"])}</div><h1>{esc(ch["name"])}</h1>'
        else:
            opener = f'<h1 class="solo">{esc(ch["label"] or ch["page"].get("title", ""))}</h1>'
        page = head(f"{short(ch)} · {title}", desc, css_href, preload, og_image=og) + f"""<body class="reading k-{ch["kind"]}">
<div class="progress" aria-hidden="true"><i></i></div>
<header class="bar"><a class="bar-home" href="index.html#toc">{esc(title)}</a><span class="bar-now">{esc(short(ch))}</span><button class="aa" type="button" aria-label="阅读设置">Aa</button></header>
{PANEL}
<main class="page">
<header class="opener">{opener}<div class="rule"></div></header>
<article class="text">
{ch["html"]}
</article>
<div class="fin" aria-hidden="true"></div>
{turn}
</main>
{colophon(info)}
<script src="reader.js" defer></script>
</body>
</html>
"""
        write(os.path.join(out, ch["slug"]), page)

    write(os.path.join(out, "404.html"), head(f"{title}", desc, "/" + css_href, []) +
          f'<body class="home"><section class="title-screen"><h1>{esc(title)}</h1><div class="rule"></div>'
          f'<div class="s">此页不存在</div><div class="y"><a href="/">回到封面</a></div></section></body></html>')
    write(os.path.join(out, ".nojekyll"), "")
    # 内容指纹：内容没变时，自动任务就不重复发布
    h = hashlib.sha256()
    for dp, _, fs in sorted(os.walk(out)):
        for f in sorted(fs):
            fp = os.path.join(dp, f)
            h.update(os.path.relpath(fp, out).encode())
            h.update(open(fp, "rb").read())
    write(os.path.join(out, "hash.txt"), h.hexdigest() + "\n")
    write(os.path.join(out, "build.txt"), datetime.datetime.now(TZ).isoformat() + "\n")
    if site_url:
        host = re.sub(r"^https?://", "", site_url).strip("/")
        if host and "github.io" not in host:
            write(os.path.join(out, "CNAME"), host + "\n")
    print(f"✓ 已生成 {len(chapters)} 个章节，最后更新 {cn_date(updated)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_site")
    ap.add_argument("--tree", help="本地 JSON（调试用）")
    ap.add_argument("--markdown", default=os.path.join(ROOT, "book", "Notes to Ascence.md"),
                    help="Markdown 书稿路径")
    ap.add_argument("--fonts", help="字体源文件目录")
    args = ap.parse_args()
    site_url = os.environ.get("SITE_URL", "")
    if args.tree:
        book = json.load(open(args.tree, encoding="utf-8"))
    else:
        from markdown_source import fetch_book
        book = fetch_book(args.markdown)
    build(book, args.out, args.fonts, site_url)


if __name__ == "__main__":
    main()
