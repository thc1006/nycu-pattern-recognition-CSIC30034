---
name: xelatex-cjk-report
description: Typesets the Traditional Chinese homework reports with XeLaTeX through the shared class common/prhw.cls and checks the PDF before submission. Covers the class interface (title block, figures, page limit, code appendix), Noto CJK TC font selection, matplotlib figures drawn at printed size, and the page, font and leftover-text checks that tools/build_report.py and tools/check_pdf.py run. Use when writing or fixing a report template (排版、LaTeX 錯誤、頁數限制), when a PDF shows Japanese glyph shapes, missing characters, missing minus signs or font warnings, or when the body must fit a page limit with an appendix after it.
---

# XeLaTeX 中文報告

## 報告格式

新作業的 `report/template.tex` 都用 `common/prhw.cls`：

```latex
\documentclass{prhw}
\assignment{N}
\title{題目}
\student{<<name>>}{<<sid>>}{<<email>>}
\pagelimit{5}
\begin{document}
\maketitle
...正文...
\codeappendix
...執行方式與版本...
<<code>>
\end{document}
```

- `\maketitle` 要緊接在 `\begin{document}` 後，否則編譯會停下；首頁的浮動圖不會跑到標題上方。
- `\fig{name}` 以版心寬度放入 `results/figures/name.pdf`。
- `\codeappendix` 結束正文：先換頁，把正文頁數與 `\pagelimit` 寫進 `.aux` 的 `prhw@body-end`。之後只寫執行方式與 `\codefile`，再寫 `\section` 編譯會停下。`<<code>>` 由 `build_report.py` 換成每個 `.py` 的 `\codefile{...}`。
- 少了 `\assignment`、`\student`、`\maketitle`、`\codeappendix` 或 `\codefile`，編譯都會停下。
- 缺字也會讓編譯停下（`\tracinglostchars=3`）。程式碼裡不能有希臘字母與數學符號（λ、σ、√、≤、≥），註解改用 ASCII（lambda、sqrt、<=），中文註解沒有問題。內文的 → ≤ ≈ ∞ 寫成 `$\to$`、`$\le$`、`$\approx$`、`$\infty$`（STIX Two Text 沒有這些字）。
- 節名有數學式時寫成 `\section{\texorpdfstring{$k$-NN}{k-NN} 分類器}`，否則 hyperref 的警告會讓建置停下。

`build_report.py` 編譯時報告資料夾優先，其次才是 `common/`，所以 `report/` 裡不能放另一份 `prhw.cls`，否則建置會停下。

## 字型

TeX Live 的 OTF 字型不在 fontconfig 裡，要用檔名。Noto CJK 的 `.ttc` 內含多個地區版本的字型，繁中的索引是 3，等寬繁中是 8；用 `.ttc` 檔名卻沒寫 `FontIndex` 時是索引 0，會拿到日文字形（例如「誤、戶、沒」的寫法不同）。`prhw.cls` 的設定：

```latex
\setmainfont{STIXTwoText}[Extension=.otf,UprightFont=*-Regular,BoldFont=*-Bold,ItalicFont=*-Italic,BoldItalicFont=*-BoldItalic]
\setmathfont{STIXTwoMath-Regular.otf}
\setsansfont{NotoSansCJK-Regular.ttc}[Path=/usr/share/fonts/opentype/noto/,FontIndex=3,BoldFont=NotoSansCJK-Bold.ttc,BoldFeatures={FontIndex=3}]
\setmonofont{Inconsolatazi4}[Extension=.otf,UprightFont=*-Regular,BoldFont=*-Bold,Scale=MatchLowercase]
\setCJKmainfont{NotoSerifCJK-Regular.ttc}[Path=/usr/share/fonts/opentype/noto/,FontIndex=3,BoldFont=NotoSerifCJK-Bold.ttc,BoldFeatures={FontIndex=3}]
\setCJKsansfont{NotoSansCJK-Regular.ttc}[Path=/usr/share/fonts/opentype/noto/,FontIndex=3,BoldFont=NotoSansCJK-Bold.ttc,BoldFeatures={FontIndex=3}]
\setCJKmonofont{NotoSansCJK-Regular.ttc}[Path=/usr/share/fonts/opentype/noto/,FontIndex=8]
```

`pdffonts` 顯示的 CJK 字型名稱都帶 jp（`NotoSerifCJKjp`、`NotoSansCJKjp`），因為各地區版本共用同一份 CFF，看名稱分不出繁中。要確認字形，就把「骨直誤戶沒」排出來用眼睛比對。

## 圖

- 共用樣式是 `common/prhw.mplstyle`，skeleton 的 `style()` 會載入它。以印出來的尺寸作圖（A4、左右邊界 18 mm 時寬 6.85 吋），`\fig` 以同樣寬度放入，圖上的字級就是印出來的字級（7 pt 左右）。
- 存 PDF 時 `pdf.fonttype = 42`，要配 TrueType（glyf）字型，例如 Noto Sans 的 `.ttf`。CFF 字型（Noto Sans CJK）以 Type 42 嵌入時，poppler 會報 `Mismatch between font type and embedded font file`，所以圖上不放中文。
- Noto Sans 沒有 U+2212 負號，樣式已設 `axes.unicode_minus: False`。對數軸的 `10^{-1}` 也會用到負號，在 `set_xscale("log")` 之後呼叫 `plain_log_ticks(ax.xaxis)`，刻度會顯示成 0.01、0.1、1。
- 呼叫 `style()` 之後，缺字形的警告會直接變成錯誤。

## 頁數與檢查

`build_report.py` 每次建置都會檢查下列各項，任何一項不過就停下：

- `prhw@body-end` 記下的正文頁數不超過 `\pagelimit`；題目全文有 limited to N pages 時，`\pagelimit` 要等於 N。
- LaTeX log 沒有 Warning、Overfull、Underfull、Missing character。
- `tools/check_pdf.py` 的檢查：未嵌入或 Type 3 字型、pdftoppm 轉圖時的警告、首頁的姓名（繳交版另加學號）、正文中的 `??`、未填的 `<<key>>`、殘留的 LaTeX 指令與替代字元。

單獨檢查一份 PDF（在專案根目錄執行，NAME 換成 `student.json` 裡的姓名）：

```sh
uv run tools/check_pdf.py homeworkN/PR_HWN/report/report.pdf --aux homeworkN/PR_HWN/report/report.aux \
    --max-pages 5 --require NAME
```

`report/` 裡只會有公開版（繳交版在暫存資料夾排版），學號只在 `homeworkN/submission/` 那份。`--max-pages` 要配 `--aux`，才知道正文在哪一頁結束。

HW1 沒有用 `prhw.cls`，檢查它要加 `--label body-end`，並用 HW1 建置時留下的 `homework1/PR_HW1/report/report.aux`。這個檔案不進版控，只在建過 HW1 的機器上有；不要為了它重建 HW1，那會改寫已經推上去的公開版 PDF。真的重建了，用 `git restore homework1/public/` 還原。沒有 aux 時整份都算正文，附錄的程式會被當成殘留的 LaTeX 指令。

檢查都沒有問題之後，逐頁看過公開版 `homeworkN/public/PR_HWN_姓名.pdf`。繳交版只多了首頁與 PDF 作者欄的學號，`build_report.py` 已檢查過。
