"""把仓库内的 Markdown 书稿转换为排版器使用的内容树。"""

import datetime
import hashlib
import os
import re
import subprocess


PRINCIPLE_RE = re.compile(r"^\s*\d{1,2}\s*[｜|丨]\s*.+$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
TOKEN_RE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")


def _annotations(**overrides):
    out = {
        "bold": False,
        "italic": False,
        "strikethrough": False,
        "underline": False,
        "code": False,
        "color": "default",
    }
    out.update(overrides)
    return out


def _run(text, href=None, **annotations):
    return {
        "type": "text",
        "plain_text": text,
        "href": href,
        "annotations": _annotations(**annotations),
    }


def rich_text(markdown):
    """解析书稿实际使用的少量行内 Markdown。"""
    out = []
    pos = 0
    for match in TOKEN_RE.finditer(markdown):
        if match.start() > pos:
            out.append(_run(markdown[pos:match.start()]))
        token = match.group(0)
        link = LINK_RE.fullmatch(token)
        if link:
            label, href = link.groups()
            if href.startswith("../founder/"):
                href = "archive/" + href.rsplit("/", 1)[-1]
            out.append(_run(label, href=href))
        elif token.startswith("**"):
            out.append(_run(token[2:-2], bold=True))
        elif token.startswith("*"):
            out.append(_run(token[1:-1], italic=True))
        else:
            out.append(_run(token[1:-1], code=True))
        pos = match.end()
    if pos < len(markdown):
        out.append(_run(markdown[pos:]))
    return [run for run in out if run["plain_text"]]


def _block(block_type, text, index, **extra):
    block_id = hashlib.sha1(f"{index}:{block_type}:{text}".encode()).hexdigest()[:32]
    data = {"rich_text": rich_text(text)}
    data.update(extra)
    return {
        "id": block_id,
        "type": block_type,
        block_type: data,
        "has_children": False,
    }


def _updated_time(path):
    repo_root = os.path.dirname(os.path.dirname(path))
    rel_path = os.path.relpath(path, repo_root)
    try:
        value = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI", "--", rel_path],
            cwd=repo_root,
            text=True,
        ).strip()
        if value:
            return value
    except (OSError, subprocess.CalledProcessError):
        pass
    stamp = datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc)
    return stamp.isoformat()


def fetch_book(path):
    path = os.path.abspath(path)
    lines = open(path, encoding="utf-8").read().splitlines()
    title = "一霁千山"
    blocks = []
    paragraph = []

    def flush_paragraph():
        nonlocal paragraph
        if not paragraph:
            return
        text = " ".join(part.strip() for part in paragraph).strip()
        if text:
            blocks.append(_block("paragraph", text, len(blocks)))
        paragraph = []

    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped:
            flush_paragraph()
            i += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", raw)
        if heading:
            flush_paragraph()
            level, text = len(heading.group(1)), heading.group(2).strip()
            if level == 1:
                title = text
            elif level == 2:
                blocks.append(_block("heading_1", text, len(blocks)))
            elif level == 3 and PRINCIPLE_RE.match(text):
                blocks.append(_block("heading_3", text, len(blocks)))
            else:
                blocks.append(_block("heading_2", text, len(blocks)))
            i += 1
            continue

        if re.fullmatch(r"-{3,}", stripped):
            flush_paragraph()
            block_id = hashlib.sha1(f"{i}:divider".encode()).hexdigest()[:32]
            blocks.append({"id": block_id, "type": "divider", "divider": {}, "has_children": False})
            i += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                part = lines[i].strip()[1:]
                if part.startswith(" "):
                    part = part[1:]
                quote_lines.append(part.rstrip().removesuffix("  "))
                i += 1
            blocks.append(_block("quote", "\n".join(quote_lines).strip(), len(blocks)))
            continue

        item = re.match(r"^\s*[-*+]\s+(.+)$", raw)
        if item:
            flush_paragraph()
            blocks.append(_block("bulleted_list_item", item.group(1).strip(), len(blocks)))
            i += 1
            continue

        numbered = re.match(r"^\s*\d+[.)]\s+(.+)$", raw)
        if numbered:
            flush_paragraph()
            blocks.append(_block("numbered_list_item", numbered.group(1).strip(), len(blocks)))
            i += 1
            continue

        # 扉页落款应位于最后一条分隔线之后，而不是附录正文中。
        if stripped == "*持续书写中*" and not any(line.strip() for line in lines[i + 1:]):
            flush_paragraph()
            block_id = hashlib.sha1(f"{i}:footer-divider".encode()).hexdigest()[:32]
            blocks.append({"id": block_id, "type": "divider", "divider": {}, "has_children": False})
            blocks.append(_block("paragraph", stripped, len(blocks)))
            i += 1
            continue

        paragraph.append(raw)
        i += 1

    flush_paragraph()
    return {
        "id": hashlib.sha1(path.encode()).hexdigest()[:32],
        "title": title,
        "last_edited_time": _updated_time(path),
        "blocks": blocks,
    }
