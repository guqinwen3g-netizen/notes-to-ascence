# 一霁千山 · Notes to Ascence

《一霁千山》的书籍版网站。**书稿写在 Notion 里**，这个仓库只负责把它排版成一本书，发布成网站。

## 它是怎么运转的

```
Notion「一霁千山」主页及子页面  →  GitHub Actions（每 30 分钟）  →  排版成网页  →  gh-pages 分支  →  网站
```

- 你只需要在 Notion 里写。内容有变化时，最多半小时后网站自动更新。
- 想立刻更新：打开本仓库 **Actions → 发布书籍 → Run workflow**。
- 内容没有变化时不会重复发布。

## 在 Notion 里怎么写，书里就怎么排

| Notion 里 | 书里 |
| --- | --- |
| 主页下的每个子页面 | 一章（按主页上的顺序） |
| 子页面标题「第一章　排除时尚，不是反时尚」（中间用全角空格） | 章序「第一章」+ 章名 |
| 标题为「序」「尾声　……」的子页面 | 序 / 尾声（尾声有单独的排法） |
| 主页上「附录」这一行之后的子页面 | 归入附录 |
| 二级标题 | 小节标题（同时进入目录） |
| 三级标题「01｜克制优先于极简主义」 | 原则条目（大号序号 + 标题） |
| 整段加粗 | 引句 |
| 整段加粗的英文 | 英文副句（意大利体） |
| 引用块 / 分隔线 / 图片 | 引文 / 「·　·　·」/ 插图 |
| 主页第一段文字、第一个引用块、最后一段文字 | 英文书名、题诗、扉页落款 |

## 文件

- `scripts/build.py` 排版生成器；`scripts/notion.py` 读取 Notion；`scripts/fonts.py` 字体裁剪
- `theme/style.css` 书籍样式；`theme/reader.js` 阅读交互（顶栏、进度、字号、夜读、记住读到哪里）
- `assets/cover.jpg.b64` 封面图片
- `.github/workflows/publish.yml` 自动发布

字体：正文为思源宋体（Noto Serif SC），西文为 EB Garamond，均为开源字体（SIL OFL）。构建时只保留书中用到的字，网页加载很快。

## 需要的设置

- 仓库 Secret `NOTION_TOKEN`：Notion 集成密钥（只需「读取内容」权限），并在 Notion「一霁千山」主页的「连接」里添加该集成。
- 网站由 `gh-pages` 分支提供（Settings → Pages → Deploy from a branch → `gh-pages` / root）。
- 绑定自己的域名：域名解析好之后，把 `publish.yml` 里的 `SITE_URL` 改成 `https://sylway.cloud`，下次发布会自动生成 CNAME。
