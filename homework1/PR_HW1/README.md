# PR HW1 程式與報告

報告在 [`../public/PR_HW1_蔡秀吉.pdf`](../public/PR_HW1_蔡秀吉.pdf)，前 4 頁是正文，第 5 頁起是程式附錄。這是公開版，內文、PDF 中繼資料和檔名都沒有學號。

交到 e3 的版本只留在本機：在這個資料夾放一個 `student.local.json`（內容為 `{"student_id": "你的學號"}`），`build_report.py` 會另外產生 `../submission/PR_HW1_蔡秀吉_<學號>.pdf`，首頁和 PDF 作者欄多了學號。`../submission/` 資料夾要先建立；這個腳本會在終端機印出含學號的檔名。`student.local.json` 和 `submission/` 都在 `.gitignore` 裡。

## 執行

所有指令都在專案根目錄（`nycu-pattern-recognition-CSIC30034/`）執行。Python 與套件版本由根目錄的 `pyproject.toml`、`uv.lock`、`.python-version` 固定，第一次執行時 uv 會自動建立 `.venv`。

```sh
uv run homework1/PR_HW1/check_hw1.py      # 數值檢查，約 2 秒
uv run homework1/PR_HW1/pr_hw1.py         # 全部實驗與圖，20 核心約 45 秒
uv run homework1/PR_HW1/build_report.py   # 填入數字、XeLaTeX 排版，輸出公開版（與本地繳交版）
```

只想重畫圖：`uv run homework1/PR_HW1/pr_hw1.py --plots-only`。排版需要 XeLaTeX，以及 Noto Serif/Sans CJK、STIX Two、Inconsolata 字型。

`pr_hw1.py` 會改寫 `results/` 的圖檔與 `run_info.json`，`build_report.py` 會改寫 `../public/` 的 PDF；數字沒變，檔案裡的日期與耗時也會不同。只想確認結果能重現時，照根目錄 README 的 HW1 一節把結果寫到 repo 外。不要的改動用 `git restore homework1/PR_HW1/results/ homework1/public/` 還原。

## 檔案

| 檔案 | 內容 |
|---|---|
| `pr_hw1.py` | 資料產生、1-NN、MD、PCA 白化與 ridge、LDA、全部實驗與作圖 |
| `check_hw1.py` | 與直接公式、SciPy、scikit-learn 對照的檢查 |
| `build_report.py` | 從 `results/` 計算報告中的每個數字，填入樣板後排版；文中的定性敘述也寫成 assert |
| `report/template.tex` | 報告樣板，`<<key>>` 由 `build_report.py` 取代；`report/report.*` 是建置產物，不進版控 |
| `results/results.npz` | 每個設定、每次重複的準確率與特徵值 |
| `results/run_info.json` | 種子、重複次數、參數網格、執行時間與套件版本 |
| `results/part1.json` | 第 1 題 95% 橢球內的點數 |
| `results/figures/` | 圖 1–5 的 PDF（排版用）與 PNG |

`results.npz` 的鍵是 `<資料>/<實驗>`，資料為 `syn` 或 `iris_n{0,1}_v{σ²}`（`n1` 表示四個特徵做了 z-score），陣列的前兩維是 `(分割, 重複)`，分割順序為 50/50、20/80。
