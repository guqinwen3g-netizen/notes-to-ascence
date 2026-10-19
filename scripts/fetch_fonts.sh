#!/usr/bin/env bash
# 下载排版用的字体源文件（思源宋体 Noto Serif SC + EB Garamond），已有则跳过。
set -u
d="${1:-.fontsrc}"; mkdir -p "$d"

valid() { python3 - "$1" <<'PY'
import sys
from fontTools.ttLib import TTFont
try:
    TTFont(sys.argv[1], lazy=True); sys.exit(0)
except Exception:
    sys.exit(1)
PY
}

get() {
  local name="$1"; shift
  local f="$d/$name"
  if [ -s "$f" ] && valid "$f"; then echo "· 已有 $name"; return 0; fi
  for u in "$@"; do
    if curl -fsSL --retry 3 --connect-timeout 20 -o "$f.tmp" "$u" && valid "$f.tmp"; then
      mv "$f.tmp" "$f"; echo "· 下载 $name ← $u"; return 0
    fi
  done
  rm -f "$f.tmp"; echo "· 未能下载 $name"; return 1
}

NC="notofonts/noto-cjk@main/Serif/SubsetOTF/SC"
ok=0
get NotoSerifSC-Regular.otf "https://github.com/notofonts/noto-cjk/raw/main/Serif/SubsetOTF/SC/NotoSerifSC-Regular.otf" "https://cdn.jsdelivr.net/gh/$NC/NotoSerifSC-Regular.otf" || ok=1
get NotoSerifSC-SemiBold.otf "https://github.com/notofonts/noto-cjk/raw/main/Serif/SubsetOTF/SC/NotoSerifSC-SemiBold.otf" "https://cdn.jsdelivr.net/gh/$NC/NotoSerifSC-SemiBold.otf" || ok=1
if [ $ok -ne 0 ]; then
  get NotoSerifSC-VF.ttf "https://github.com/google/fonts/raw/main/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf" || {
    echo "· 改用系统字体包"; sudo apt-get install -y -qq fonts-noto-cjk fonts-noto-cjk-extra >/dev/null 2>&1 || true; }
fi
GF="https://github.com/google/fonts/raw/main/ofl/ebgaramond"
get EBGaramond.ttf "$GF/EBGaramond%5Bwght%5D.ttf" || true
get EBGaramond-Italic.ttf "$GF/EBGaramond-Italic%5Bwght%5D.ttf" || true
exit 0
