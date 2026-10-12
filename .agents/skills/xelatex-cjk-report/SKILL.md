---
name: xelatex-cjk-report
description: Typesets Traditional Chinese reports with XeLaTeX and checks the PDF before submission, covering Noto CJK TC font selection, matplotlib figures drawn at printed size, a page limit enforced through an aux label, and embedded-font and leftover-text checks. Use when building or fixing a 中文 LaTeX/PDF report, when a PDF shows Japanese glyph shapes, missing minus signs or font warnings, or when the body must fit a page limit with an appendix after it.
---

# XeLaTeX 中文報告

## 字型

TeX Live 的 OTF 字型不在 fontconfig 裡，要用檔名；Noto CJK 的 `.ttc` 內含多個地區字面，繁中是第 3 個（等寬繁中是第 8 個）。用家族名稱或索引 0 會拿到日文字形（例如「誤、戶、沒」的寫法不同）。

```latex
\usepackage{fontspec}\usepackage{xeCJK}\usepackage{amsmath}\usepackage{unicode-math}
\setmainfont{STIXTwoText}[Extension=.otf,UprightFont=*-Regular,BoldFont=*-Bold,ItalicFont=*-Italic,BoldItalicFont=*-BoldItalic]
\setmathfont{STIXTwoMath-Regular.otf}
\setmonofont{Inconsolatazi4}[Extension=.otf,UprightFont=*-Regular,BoldFont=*-Bold,Scale=MatchLowercase]
\setCJKmainfont{NotoSerifCJK-Regular.ttc}[Path=/usr/share/fonts/opentype/noto/,FontIndex=3,BoldFont=NotoSerifCJK-Bold.ttc,BoldFeatures={FontIndex=3}]
\setCJKsansfont{NotoSansCJK-Regular.ttc}[Path=/usr/share/fonts/opentype/noto/,FontIndex=3,BoldFont=NotoSansCJK-Bold.ttc,BoldFeatures={FontIndex=3}]
```

`pdffonts` 顯示的嵌入名稱一律是 `NotoSerifCJKjp`（各字面共用同一份 CFF），要確認字形，就把「骨直誤戶沒」排出來用眼睛比對。

## 圖

- 以印出來的尺寸作圖（A4、左右邊界 18 mm 時寬 6.85 吋），LaTeX 用 `width=\linewidth` 放入，字級就是實際字級（7 pt 左右）。
- 存 PDF 時 `pdf.fonttype = 42`，並選 TrueType（glyf）字型，例如 Noto Sans 的 `.ttf`。CFF 字型（Noto Sans CJK）以 Type 42 嵌入時，poppler 會報 `Mismatch between font type and embedded font file`。
- Noto Sans 沒有 U+2212 負號：設 `axes.unicode_minus = False`；對數軸的 `10^{-1}` 也會用到負號，改用 `FuncFormatter(lambda t, _: f"{t:g}")` 顯示 0.01、0.1、1。
- 繪圖後讀一次所有警告；`Glyph ... missing` 一定要處理。

## 頁數限制

在正文最後一句後放 `\label{body-end}`，附錄前 `\clearpage`。編譯兩次後從 `.aux` 讀頁碼：

```
\newlabel{body-end}{{7}{5}{...}{section.7}{}}   ← 第二組大括號是頁碼
```

首頁不要讓浮動圖跑到標題上方：標題後加 `\suppressfloats[t]`。

## 檢查

```sh
uv run .agents/skills/xelatex-cjk-report/scripts/check_pdf.py report.pdf --aux report.aux \
    --label body-end --max-pages 5 --require 姓名 --require 學號
```

會檢查：正文頁數、未嵌入或 Type 3 字型、繪圖器警告、首頁必備文字、正文中的 `??`、未填的 `<<key>>`、殘留的 LaTeX 指令與替代字元。全部通過才交出去，並且逐頁看一次 PNG（`pdftoppm -r 80 -png`）。
