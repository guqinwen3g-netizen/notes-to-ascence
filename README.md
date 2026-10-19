# 一霁千山 · Notes to Ascence

《一霁千山》的书籍版网站。正式书稿保存在仓库内的 `book/Notes to Ascence.md`，网站由这份 Markdown 自动排版生成。

## 它是怎么运转的

```
book/Notes to Ascence.md  →  GitHub Actions  →  排版成网页  →  gh-pages 分支  →  网站
```

- 更新 `book/Notes to Ascence.md` 并推送到 `main` 后，网站会自动更新。
- 需要重新发布时，也可以打开本仓库 **Actions → 发布书籍 → Run workflow**。
- 内容没有变化时不会重复发布。

## Markdown 怎么写，书里就怎么排

| Markdown 里 | 书里 |
| --- | --- |
| 文档标题 `# 一霁千山` | 书名 |
| 二级标题 `## 第一章　自在从容，方能长久` | 一章，拆分为章序与章名 |
| 标题为 `## 序`、`## 尾声　……` | 序或尾声 |
| 三级标题 `### 01｜排除时尚，不是反时尚` | Doctrine 条目（大号序号 + 标题） |
| 四级标题 | Doctrine 内的小节标题，同时进入目录 |
| 整段加粗 | 引句 |
| 整段加粗的英文 | 英文副句（意大利体） |
| 引用块 / 分隔线 / 图片 | 引文 / 「·　·　·」/ 插图 |
| 书名后的第一段、第二段、第一个引用块、最后一段 | 英文书名、署名、题诗、扉页落款 |

## 文件

- `book/Notes to Ascence.md` 正式书稿
- `scripts/build.py` 排版生成器；`scripts/markdown_source.py` 读取 Markdown；`scripts/fonts.py` 字体裁剪
- `theme/style.css` 书籍样式；`theme/reader.js` 阅读交互（顶栏、进度、字号、夜读、记住读到哪里）
- `assets/cover.jpg.b64` 封面图片
- `.github/workflows/publish.yml` 自动发布

字体：正文为思源宋体（Noto Serif SC），西文为 EB Garamond，均为开源字体（SIL OFL）。构建时只保留书中用到的字，网页加载很快。

## 发布设置

- 网站由 `gh-pages` 分支提供（Settings → Pages → Deploy from a branch → `gh-pages` / root）。
- 绑定自己的域名：域名解析好之后，把 `publish.yml` 里的 `SITE_URL` 改成 `https://sylway.cloud`，下次发布会自动生成 CNAME。
