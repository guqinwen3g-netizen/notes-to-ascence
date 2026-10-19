"""从 Notion 读取整本书（主页 + 各章节子页面）。

只依赖 Python 标准库。需要环境变量 NOTION_TOKEN（Notion 集成密钥）。
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"


class Notion:
    def __init__(self, token):
        self.token = token

    def _get(self, path, params=None):
        url = API + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for attempt in range(7):
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": VERSION,
            })
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 6:
                    wait = float(e.headers.get("Retry-After") or 2 ** attempt)
                    time.sleep(min(wait, 30))
                    continue
                body = e.read().decode("utf-8", "replace")[:600]
                if e.code in (401, 403, 404):
                    raise SystemExit(
                        f"Notion API {e.code}：{body}\n"
                        "请确认：① NOTION_TOKEN 正确；② 已在 Notion 主页「•••」→「连接」里添加了这个集成。")
                raise SystemExit(f"Notion API {e.code}: {body}")
            except urllib.error.URLError:
                if attempt < 6:
                    time.sleep(2 ** attempt)
                    continue
                raise

    def page(self, page_id):
        return self._get(f"/pages/{page_id}")

    def children(self, block_id):
        out, cursor = [], None
        while True:
            params = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            data = self._get(f"/blocks/{block_id}/children", params)
            out.extend(data.get("results", []))
            if not data.get("has_more"):
                return out
            cursor = data.get("next_cursor")

    def tree(self, block_id, expand_pages=False):
        blocks = self.children(block_id)
        for b in blocks:
            t = b.get("type")
            if t == "child_page":
                if expand_pages:
                    b["page"] = {
                        "id": b["id"],
                        "title": b["child_page"].get("title", ""),
                        "blocks": self.tree(b["id"]),
                    }
                continue
            if t in ("child_database", "unsupported"):
                continue
            if b.get("has_children"):
                src = b["id"]
                if t == "synced_block":
                    sf = (b.get("synced_block") or {}).get("synced_from")
                    if sf and sf.get("block_id"):
                        src = sf["block_id"]
                b["children"] = self.tree(src)
        return blocks


def page_title(page):
    for prop in (page.get("properties") or {}).values():
        if prop.get("type") == "title":
            return "".join(x.get("plain_text", "") for x in prop.get("title", []))
    return ""


def fetch_book(token, root_id):
    n = Notion(token)
    root = n.page(root_id)
    return {
        "id": root["id"],
        "title": page_title(root),
        "last_edited_time": root.get("last_edited_time"),
        "blocks": n.tree(root_id, expand_pages=True),
    }
