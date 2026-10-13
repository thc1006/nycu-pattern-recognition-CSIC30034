# 圖形識別作業

陽明交大 115 學年度上學期「圖形識別」（CSIC30034）的作業程式、實驗結果與報告。

## 環境

Python 與套件版本由 `.python-version`、`pyproject.toml`、`uv.lock` 固定。所有指令都在專案根目錄用 uv 執行，第一次執行時 uv 會建立 `.venv`：

```sh
uv sync --locked
```

排版、作圖與檢查 PDF 用到的系統套件（Debian/Ubuntu）：

```sh
sudo apt install texlive-xetex texlive-latex-extra texlive-lang-cjk texlive-fonts-extra \
    fonts-noto-cjk fonts-noto-core poppler-utils
```

`tools/build_report.py` 與 `tools/scan_private.py` 都會用到 poppler-utils。

## 目錄結構

| 路徑 | 內容 |
|---|---|
| `homework1/` | HW1 的題目、程式、結果，報告公開版在 `homework1/public/` |
| `material/pdf/` | 講義 |
| `common/prhw.cls` | 報告的 LaTeX 格式：字型、版面、首頁、頁數限制、程式附錄 |
| `common/prhw.mplstyle` | 圖的樣式 |
| `common/skeleton/` | 新作業的起始檔案 |
| `tools/new_homework.py` | 從 `common/skeleton/` 建立 `homeworkN/PR_HWN/` |
| `tools/build_report.py` | 填入數字、排版、檢查，輸出繳交版與公開版 PDF |
| `tools/check_pdf.py` | 檢查 PDF 的頁數、字型與殘留文字 |
| `tools/scan_private.py` | commit 前檢查學號有沒有外流 |
| `tools/compare_npz.py` | 比對兩次執行的 `results.npz` |
| `tools/scan_zh_style.py` | 找出中文稿裡的套話、標點習慣與大陸用語 |
| `student.json` | 報告首頁的姓名與信箱 |

## 新作業

```sh
uv run tools/new_homework.py 2
```

這會建立 `homework2/PR_HW2/`。接著把題目存成 `homework2/PR_HW2.pdf`，全文轉成 `homework2/PR_HW2_full_transcription.md`，在 `homework2/PR_HW2/report/template.tex` 填 `\title` 與 `\pagelimit`，再把範例實驗、範例數字與範例段落換成這次的內容。然後：

```sh
uv run homework2/PR_HW2/check_hw2.py    # 數值檢查
uv run homework2/PR_HW2/pr_hw2.py       # 實驗與圖
uv run tools/build_report.py 2          # 報告
```

`build_report.py` 從全文找 limited to N pages 這種寫法，找到的頁數和 `\pagelimit` 不同時會停下。找不到時只印出提示並以 `\pagelimit` 為準，要自己對照題目。

## 學號

學號不進版控，只寫在被 `.gitignore` 排除的 `*.local.json`（內容是 `{"student_id": "..."}`）。新作業用根目錄的 `student.local.json`，HW1 用 `homework1/PR_HW1/student.local.json`。有學號時，`build_report.py` 產生兩份 PDF：

- `homeworkN/submission/PR_HWN_姓名_學號.pdf` 交到 e3，只留在本機。
- `homeworkN/public/PR_HWN_姓名.pdf` 推上 GitHub，內文、中繼資料與檔名都沒有學號。

commit 前執行 `uv run tools/scan_private.py`，它會檢查暫存區與尚未推送的 commit，包括其中的 PDF。

## 交件版本

每次交件後打一個 tag，日後改了 `common/` 或 `tools/` 也找得回交出去的版本。HW1 的 tag 是 `hw1`，HW2 交件後：

```sh
git tag -a hw2 -m "HW2 as submitted"
git push origin hw2
```

## HW1

HW1 做的時候還沒有 `common/` 與 `tools/build_report.py`，所以用的是自己的 `homework1/PR_HW1/build_report.py`。
