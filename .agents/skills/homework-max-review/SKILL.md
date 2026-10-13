---
name: homework-max-review
description: Runs the strict pre-submission review of a finished homework assignment (code, saved results, figures and report PDF). Checks every requirement against the assignment text, the code against independent references, every number and claim against saved output, a rerun from a clean checkout that must match the saved results bit for bit, figures and captions, writing style, the page limit and the code appendix. Use before submitting any homework PDF (交件前檢查、嚴格審查、最終檢查).
---

# 交件前審查

審查分成幾輪，每輪都要留下證據（指令輸出、比對結果）。發現問題就修，修完從受影響的那一輪往後重跑，直到重跑完都沒有新問題。

## 第 1 輪：需求逐條對照

把題目全文每一句列成表：要求、報告中的位置（節、圖、表）、證據。任何一列缺位置或證據就是問題。特別檢查容易漏的項目，以 HW1 為例：兩種分割都做了、訓練與測試曲線都有、指定的變數範圍（例如 1 到 100）有完整掃過、題目提到的比較（有無標準化、不同雜訊變異數、LDA 對 rLDA、LDA 對 PCA）各自有數字與分析、頁數限制、附錄程式、姓名學號。

## 第 2 輪：程式正確性

- 執行作業的檢查腳本 `uv run homeworkN/PR_HWN/check_hwN.py`。
- 逐函式讀程式，對照講義公式：共變異數的分母、散布矩陣的權重、白化的縮放、ridge 加的位置、奇異時的處理、只用訓練集估計。
- 找邊界情形：秩不足、全 NaN 欄位、類別順序、平手、亂數串流是否在不同方法間共用。
- 隔一段時間再從頭讀一次程式，只記下能重現的錯誤。

## 第 3 輪：乾淨重跑

先照 `privacy-safe-commits` 把程式與結果 commit（還不用推送），在只含已 commit 檔案的 worktree 裡依鎖檔重建環境、重跑實驗，結果寫到新的暫存資料夾。指令用 `&&` 串起來，worktree 建不起來時不會改在原本的資料夾重跑：

```sh
root=$(pwd)
git worktree prune
git worktree add --detach ../rerun HEAD && cd ../rerun && uv sync --locked &&
  out=$(mktemp -d) && uv run homeworkN/PR_HWN/pr_hwN.py --out "$out" &&
  uv run tools/compare_npz.py "$root/homeworkN/PR_HWN/results/results.npz" "$out/results.npz"
cd "$root" && git worktree remove ../rerun
```

結果必須逐位相同（同一台機器、同一份鎖檔）。不同就找出原因，不要只放寬容許誤差。

## 第 4 輪：數字與敘述

- 報告數字全部由 `report_numbers.py` 從結果檔算出、`tools/build_report.py` 填入。用 `grep -nE '[0-9]' homeworkN/PR_HWN/report/template.tex` 列出樣板裡的每個數字，逐一確認是題號、檔名或常數。
- 每一句定性敘述（誰比較好、何時重合、在哪裡最低）都要在 `report_numbers.py` 有對應的 assert，或有親手算出的數字；做不到就改寫或刪除。
- 理論說明（例如不變性、秩的上界、隨機矩陣的特徵值範圍）用小實驗驗證一次。
- 拿 PDF 和 `results.npz` 逐句核對，找出對不上的數字和推論過頭的句子。

## 第 5 輪：圖與 PDF

- 逐頁檢視公開版 `homeworkN/public/PR_HWN_姓名.pdf`：圖例不壓到曲線、標籤不被裁切、圖在正確的節附近、首頁標題在最上方。繳交版只多了首頁與 PDF 作者欄的學號，`build_report.py` 已檢查過。
- 圖說只描述畫了什麼（資料、分割、重複次數、色帶意義），不放詮釋。
- `uv run tools/build_report.py N` 沒有任何錯誤（它會跑 `tools/check_pdf.py` 的全部檢查）；附錄的程式就是實際執行的那份（`\codefile` 直接讀原檔）。

## 第 6 輪：文字

- `uv run tools/scan_zh_style.py homeworkN/PR_HWN/report/template.tex` 沒有提示，或每筆都確認過。
- 通讀一次：每段的第一句是事實、最後一句停在結果；術語前後一致；沒有與實驗無關的句子。

詳細檢查項目：`references/review-checklist.md`。
