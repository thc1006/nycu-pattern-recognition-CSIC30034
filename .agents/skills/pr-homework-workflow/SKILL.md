---
name: pr-homework-workflow
description: End-to-end workflow for an NYCU Pattern Recognition homework assignment in this repo, from the assignment text to the e3 PDF and the public PDF. Starts homeworkN/PR_HWN/ from common/skeleton with tools/new_homework.py, implements the methods in NumPy under uv, runs seeded repeated experiments in parallel, draws figures in the shared style, and builds the report with tools/build_report.py, which fills every number from saved results, enforces the page limit and keeps the student ID out of the public PDF. Use when starting, continuing or finishing an assignment (HW2, homework 3; 開新作業、實作、報告、繳交 PDF).
---

# 圖形識別作業流程

新作業從 `common/skeleton/` 開始。`homework1/PR_HW1/` 是已交的完整例子，可以參考它的實驗與寫法，但它做的時候還沒有共用格式，樣板與建置腳本都是它自己的。

## 1. 開新作業

```sh
uv run tools/new_homework.py N
```

這會建立 `homeworkN/PR_HWN/`，檔名、import、路徑與 `\assignment{N}` 裡的 N 都換成這次的作業編號。接著：

- 題目存成 `homeworkN/PR_HWN.pdf`，題目全文轉成 `homeworkN/PR_HWN_full_transcription.md`。`build_report.py` 從題目全文找 limited to N pages 讀出頁數限制；換了說法就找不到，只印出提示並沿用 `\pagelimit`。題目 PDF 有權限保護（`pdfinfo` 顯示 `Encrypted: yes`）時，掃描讀不了，commit 會被擋下；用 `pdftocairo -pdf 原檔.pdf homeworkN/PR_HWN.pdf` 另存一份沒有加密的。
- 在 `report/template.tex` 填 `\title` 與 `\pagelimit`。
- skeleton 的範例實驗、範例數字與範例段落全部換掉。

修改 skeleton 時，作業編號寫成 N，並緊接在 homework、HW、hw 或 `\assignment{` 之後（例如 `PR_HWN`、`check_hwN`、`\assignment{N}`），或寫成 `build_report.py N`。其他地方只要有單獨的大寫 N（例如 `$N$`、`HW N`、變數 N），`new_homework.py` 就會停下，不寫任何檔案。

## 2. 讀題

- 把題目的要求逐句列成清單，每列寫要求、我的做法、輸出的圖或數字，最後審查時逐列打勾。
- 讀相關的講義頁（`material/pdf/`；逐頁文字版 `material/PR_Set0*.md` 不進版控，只在原本的電腦上，換電腦要另外複製），記下老師的定義與記號（例如 Mahalanobis 距離（MD）分類器用各類共變異數、`S_w=ΣP_iΣ_i`、ridge 寫成 `Σ+γI`）。

## 3. 實作

- 環境照 `uv-locked-python`；核心估計只用 NumPy，scikit-learn 只載資料或拿來對照。
- 所有平均數、共變異數、標準化、PCA、LDA 只用訓練集估計。
- `pr_hwN.py` 的 `run_task(rep)` 是一次重複，`run_all` 用 process pool 平行跑完 `REPEATS` 次。每次重複都重新產生資料與分割，同一次重複內各方法共用同一個分割，比較才是成對的。
- 亂數一律來自 `default_rng([SEED, rep, k])`，每個用途一個 k，從 1 開始，因為 `[SEED, rep, 0]` 和 `[SEED, rep]` 是同一串亂數。
- 遇到奇異矩陣要在報告中講清楚處理方式（擬反矩陣、ridge、限制維度），並在圖上標出奇異區。
- `check_hwN.py` 把 `pr_hwN.py` 的每個函式和直接公式、SciPy、scikit-learn 比對。
- 結果存在 `results/`：`results.npz`（第一維是重複）與 `run_info.json`（種子、重複次數、網格、行程數、耗時、套件版本）。`load()` 讀結果時，`SEED`、`REPEATS` 或 `SIZES` 和程式不同就停下。換掉範例實驗時，新的參數網格（例如 `GAMMAS`）也寫進 `run_info.json` 並加進 `load()` 的比對；用到其他會影響數值的套件時，版本也寫進 `run_info.json`，並加進 `report_numbers.py` 的比對。
- 作圖先呼叫 `style()`，它套用 `common/prhw.mplstyle`，缺字形時直接停下。寬度用 `TEXT_WIDTH`；對數軸呼叫 `plain_log_ticks`；`save()` 同時存 PDF 與 PNG，重畫時 PDF 的位元組不變。圖上的文字用英文。

## 4. 報告

- `report_numbers.py` 從結果算出報告引用的每個數字，以字串放進 `v`。文中的定性敘述（「A 在每個 σ² 都低於 B」「曲線在可逆區完全重合」）同時寫成 assert，結果變了、敘述不再成立時就會停下。它也比對 `run_info.json` 記下的套件版本，和目前環境不同時停下。
- `report/template.tex` 用 `common/prhw.cls`（介面見 `xelatex-cjk-report`），數字一律寫成 `<<key>>`。每題一節，節名寫題號；每節依序寫結果、預期、原因。文字規範照 `zh-tw-technical-writing`。
- 建置：

  ```sh
  uv run tools/build_report.py N
  ```

  它執行 `report_numbers.py` 並把 `v` 填入樣板，樣板用到卻沒算、算了卻沒用的 key，建置都會停下；附錄放入作業資料夾裡的每個 `.py`（git 忽略的除外）。接著用 XeLaTeX 排出繳交版與公開版，檢查頁數、字型、LaTeX 警告與殘留文字，兩份都沒有問題才一起寫出：
  - `homeworkN/submission/PR_HWN_姓名_學號.pdf`：交 e3，被 git 忽略。
  - `homeworkN/public/PR_HWN_姓名.pdf`：推上 GitHub，內文、中繼資料、檔名都沒有學號。
- 姓名與信箱在根目錄的 `student.json`，學號只在被忽略的 `student.local.json`（見 `privacy-safe-commits`）。

## 5. 交件前

照 `homework-max-review` 做完整審查，至少包含乾淨環境重跑、數字逐一比對與需求清單打勾。之後照 `privacy-safe-commits` 分批 commit 與推送。
