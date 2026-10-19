"""把字体裁剪成「只包含本书用到的字」的网页字体，让中文宋体也能快速加载。"""
import os

LATIN_RANGE = "U+0020-007E,U+00A0-00FF,U+0131,U+0152-0153,U+2122"
LATIN_CODES = list(range(0x20, 0x7F)) + list(range(0xA0, 0x100)) + [0x131, 0x152, 0x153, 0x2122]

# (字体族, 字重, 样式, 源文件名, 输出文件名, 用途)
SPECS = [
    ("AS Serif", "400", "normal", "NotoSerifSC-Regular.otf", "serif-400", "all"),
    ("AS Serif", "600", "normal", "NotoSerifSC-SemiBold.otf", "serif-600", "bold"),
    ("AS Latin", "400 800", "normal", "EBGaramond.ttf", "latin", "latin"),
    ("AS Latin", "400 800", "italic", "EBGaramond-Italic.ttf", "latin-italic", "latin"),
]
# 找不到静态字体时的备选：可变字体 / 系统里的 Noto Serif CJK 合集
VF_NAME = "NotoSerifSC-VF.ttf"
TTC_NAMES = {"400": ["NotoSerifCJK-Regular.ttc"], "600": ["NotoSerifCJK-SemiBold.ttc", "NotoSerifCJK-Bold.ttc"]}
TTC_DIRS = ["/usr/share/fonts/opentype/noto", "/usr/share/fonts/google-noto-cjk", "/usr/share/fonts/noto-cjk",
            "/usr/share/fonts/truetype/noto", "/usr/share/fonts/opentype"]

PUNCT = "，。、；：？！“”‘’（）《》〈〉【】「」『』—…·－～　0123456789"


def _flavor():
    try:
        import brotli  # noqa: F401
        return "woff2"
    except ImportError:
        return "woff"


def _open(path, **kw):
    from fontTools.ttLib import TTFont
    return TTFont(path, recalcTimestamp=False, **kw)


def _load_cjk(src_dir, src, weight):
    """依次尝试：静态 OTF → 可变字体实例 → 系统 TTC 中的简体中文字面。"""
    path = os.path.join(src_dir or "", src)
    if src_dir and os.path.exists(path):
        try:
            return _open(path), src
        except Exception as e:
            print(f"· {src} 无法读取（{e}）")
    vf = os.path.join(src_dir or "", VF_NAME)
    if src_dir and os.path.exists(vf):
        try:
            from fontTools.varLib import instancer
            return instancer.instantiateVariableFont(_open(vf), {"wght": int(weight)}), VF_NAME
        except Exception as e:
            print(f"· 可变字体实例化失败（{e}）")
    for d in TTC_DIRS:
        for name in TTC_NAMES.get(weight, []):
            p = os.path.join(d, name)
            if not os.path.exists(p):
                continue
            try:
                from fontTools.ttLib import TTCollection
                for i, f in enumerate(TTCollection(p).fonts):
                    if " SC" in (f["name"].getDebugName(1) or ""):
                        return _open(p, fontNumber=i), name
            except Exception as e:
                print(f"· {name} 读取失败（{e}）")
    return None, None


def build_fonts(src_dir, out_dir, all_text, bold_text):
    """返回 @font-face CSS；找不到源字体时跳过（网页会退回系统宋体）。"""
    try:
        from fontTools import subset
        import fontTools.ttLib  # noqa: F401
    except ImportError:
        print("· 未安装 fonttools，跳过网页字体")
        return ""
    os.makedirs(out_dir, exist_ok=True)
    flavor = _flavor()
    css = []
    base = set(PUNCT) | {chr(c) for c in range(0x20, 0x7F)}
    for family, weight, style, src, name, use in SPECS:
        if family == "AS Serif":
            font, used = _load_cjk(src_dir, src, weight)
        else:
            font, used = None, src
            path = os.path.join(src_dir or "", src)
            if src_dir and os.path.exists(path):
                try:
                    font = _open(path)
                except Exception as e:
                    print(f"· {src} 无法读取（{e}）")
        if font is None:
            print(f"· 缺少 {src}，跳过（网页会使用系统字体）")
            continue
        if use == "latin":
            codes = LATIN_CODES
        else:
            chars = set(all_text if use == "all" else bold_text) | base
            codes = sorted(ord(c) for c in chars if not c.isspace() or c == "　")
        opts = subset.Options()
        opts.flavor = flavor
        opts.layout_features = ["*"]
        opts.name_IDs = ["*"]
        opts.notdef_outline = True
        opts.hinting = False
        opts.desubroutinize = True
        sub = subset.Subsetter(options=opts)
        sub.populate(unicodes=codes)
        sub.subset(font)
        fn = f"{name}.{flavor}"
        font.flavor = flavor
        font.save(os.path.join(out_dir, fn))
        kb = os.path.getsize(os.path.join(out_dir, fn)) // 1024
        print(f"· 字体 {fn}：{kb} KB（来源 {used}）")
        extra = ""
        if family == "AS Latin":
            extra = f"unicode-range:{LATIN_RANGE};size-adjust:110%;"
        css.append(
            f'@font-face{{font-family:"{family}";font-weight:{weight};font-style:{style};'
            f'font-display:swap;src:url(fonts/{fn}) format("{flavor}");{extra}}}')
    return "\n".join(css)
