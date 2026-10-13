# 圖形識別作業

陽明交大 115 學年度上學期「圖形識別」（CSIC30034）的作業程式、實驗結果與報告。

## 環境

Python 與套件版本由 `.python-version`、`pyproject.toml`、`uv.lock` 固定。所有指令都在專案根目錄用 [uv](https://docs.astral.sh/uv/) 執行，第一次執行時 uv 會建立 `.venv`：

```sh
uv sync --locked
```

排版、作圖與檢查 PDF 用到的系統套件（Debian/Ubuntu）：

```sh
sudo apt install texlive-xetex texlive-latex-extra texlive-lang-cjk texlive-fonts-extra \
    fonts-noto-cjk fonts-noto-core poppler-utils
```

`tools/build_report.py` 與 `tools/scan_private.py` 都會用到 poppler-utils。`common/prhw.cls` 從 `/usr/share/fonts/opentype/noto/` 載入 Noto CJK，字型裝在別的路徑時，要改 `prhw.cls` 裡的 `Path=`。

要 commit 或產生交 e3 的 PDF，第一次 clone 之後先照「學號」一節建立 `student.local.json`；要 commit 的話再安裝 hook。

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
| `tools/scan_private.py` | commit 與 push 前檢查學號有沒有外流，也能裝成 git hook |
| `tools/compare_npz.py` | 比對兩次執行的 `results.npz` |
| `tools/scan_zh_style.py` | 找出中文稿裡的套話、標點習慣與大陸用語 |
| `student.json` | 報告首頁的姓名與信箱 |

## 新作業

```sh
uv run tools/new_homework.py 2
```

這會建立 `homework2/PR_HW2/`。接著把題目存成 `homework2/PR_HW2.pdf`，題目全文轉成 `homework2/PR_HW2_full_transcription.md`，在 `homework2/PR_HW2/report/template.tex` 填 `\title` 與 `\pagelimit`，再把範例實驗、範例數字與範例段落換成這次的內容。報告首頁的姓名與信箱來自根目錄的 `student.json`，拿這個 repo 去用的人要先換成自己的。然後：

```sh
uv run homework2/PR_HW2/check_hw2.py    # 數值檢查
uv run homework2/PR_HW2/pr_hw2.py       # 實驗與圖
uv run tools/build_report.py 2          # 報告
```

`build_report.py` 從題目全文找 limited to N pages 這種寫法，找到的頁數和 `\pagelimit` 不同時會停下。找不到時只印出提示並以 `\pagelimit` 為準，要自己對照題目。題目 PDF 有權限保護（`pdfinfo` 顯示 `Encrypted: yes`）時，掃描讀不了，commit 會被擋下；用 `pdftocairo -pdf 原檔.pdf homeworkN/PR_HWN.pdf` 另存一份沒有加密的。每次執行 `build_report.py`，公開版 PDF 裡的日期都會更新，內容沒變也會出現在 `git status`；不需要更新時，用 `git restore homeworkN/public/` 還原。

## 學號

學號不進版控，只寫在被 `.gitignore` 排除的 `*.local.json`（內容是 `{"student_id": "..."}`）。新作業用根目錄的 `student.local.json`，HW1 用 `homework1/PR_HW1/student.local.json`。有學號時，`build_report.py` 產生兩份 PDF：

- `homeworkN/submission/PR_HWN_姓名_學號.pdf` 交到 e3（學校的線上教學平台），只留在本機。
- `homeworkN/public/PR_HWN_姓名.pdf` 推上 GitHub，內文、中繼資料與檔名都沒有學號。

clone 之後執行一次 `uv run tools/scan_private.py --install-hooks`，`tools/scan_private.py` 有更新之後再執行一次。這個指令把三個 hook 與掃描程式的複本寫進 `.git/hooks/`。之後每次 `git commit` 前，git 用這份複本檢查暫存區、commit 訊息、author 與 committer；每次 push 前檢查要送出的檔案、commit、tag 與分支名稱，`git merge`、`cherry-pick`、`rebase`、`am` 做出的 commit 只在這時檢查。在 `git worktree` 開的工作目錄、切到沒有 `tools/` 的舊 commit，或 repo 資料夾搬走之後，也照樣檢查。設定了 `core.hooksPath`，或 `.git/hooks/` 裡已經有同名的其他 hook 時，安裝會停下並說明原因。hook 沒有生效時，手動執行 `tools/scan_private.py` 或 `tools/build_report.py` 會印出提示。

檔案內容、檔名、commit 訊息、author、committer、tag 或分支名稱出現 `*.local.json` 裡的值，有認得格式卻讀不了的檔案（例如加密的 PDF、7z），或 commit 訊息不是純文字（`Signed-off-by:`、`Change-Id:` 這類 trailer、emoji、Markdown 連結），都會停下。圖片裡的字，以及 `.mat`、HDF5、Parquet 這類格式裡壓縮過的資料，掃描讀不到，也不會擋下。沒有任何 `*.local.json`，或裡面的值都短於 4 個字元時，每次 commit 與 push 都會被擋下，要先建立自己的 `student.local.json`。只想跑程式、不會 commit 的人不用裝 hook。要移除 hook，刪掉 `.git/hooks/` 裡的 `pre-commit`、`commit-msg`、`pre-push` 與 `scan_private.py`。

`*.local.json`、`homework*/submission/` 裡交出去的 PDF，以及 `.gitignore` 裡 local only 那幾項（例如講義的逐頁文字版 `material/PR_Set*.md`）都不在 GitHub 上，換電腦時要自己複製過去。

## HW1

HW1 做的時候還沒有 `common/` 與 `tools/build_report.py`，所以用的是自己的 `homework1/PR_HW1/build_report.py`，交出去的是 commit ce1870b 的版本。要確認結果能重現，重跑實驗並把結果寫到 repo 外的資料夾，再和存好的結果比對：

```sh
out=$(mktemp -d)
uv run homework1/PR_HW1/pr_hw1.py --out "$out"
uv run tools/compare_npz.py homework1/PR_HW1/results/results.npz "$out/results.npz"
cmp homework1/PR_HW1/results/part1.json "$out/part1.json"
```

不加 `--out` 重跑，會改寫圖檔 PDF 裡的日期與 `run_info.json` 的耗時；重跑 `homework1/PR_HW1/build_report.py` 會改寫公開版 PDF 裡的日期，建完用 `git restore homework1/public/` 還原。在新的 clone 裡要建 HW1 的繳交版，先建立 `homework1/submission/` 資料夾。

## 授權

`material/pdf/` 的講義、各次作業的題目（`homeworkN/PR_HWN.pdf`）與題目全文（`homeworkN/PR_HWN_full_transcription.md`），以及老師隨作業提供的其他檔案，著作權屬於授課老師，不在授權範圍內。其餘內容（程式、說明、報告、圖與實驗結果）依 [Apache-2.0](LICENSE) 授權。

The lecture slides in `material/pdf/`, the assignment handouts (`homeworkN/PR_HWN.pdf`) and their transcriptions (`homeworkN/PR_HWN_full_transcription.md`), and any other files the instructor provides with an assignment, belong to the instructor and are not covered by the license. Everything else in this repository is licensed under [Apache-2.0](LICENSE).
