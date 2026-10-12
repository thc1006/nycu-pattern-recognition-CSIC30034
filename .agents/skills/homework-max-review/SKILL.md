---
name: homework-max-review
description: Runs a maximum-rigor review of a finished homework submission (code, saved results, figures and report PDF) before it is handed in. Covers requirement coverage, numerical correctness against independent references, every number and claim traced to saved output, clean-room reproduction, figure and caption checks, writing-style scan, page limit and appendix integrity. Use when asked for a deep, strict or max-rigor review, 嚴格審查、最終檢查、再審一次, or before submitting any homework PDF.
---

# 交件前的最嚴格審查

審查分成幾輪，每輪都要留下證據（指令輸出、比對結果）。發現問題就修，修完從受影響的那一輪重跑，直到某一輪找不到新問題。

## 第 1 輪：需求逐條對照

把題目原文每一句列成表：要求、報告中的位置（節、圖、表）、證據。缺任何一列就是問題。特別檢查容易漏的：兩種分割都做了、訓練與測試曲線都有、指定的變數範圍（例如 1 到 100）有完整掃過、題目提到的比較（有無標準化、不同雜訊變異數、LDA 對 rLDA、LDA 對 PCA）各自有數字與分析、頁數限制、附錄程式、姓名學號。

## 第 2 輪：程式正確性

- 執行專案的檢查腳本（例如 `uv run homework1/PR_HW1/check_hw1.py`）。
- 逐函式讀程式，對照講義公式：共變異數的分母、散布矩陣的權重、白化的縮放、ridge 加的位置、奇異時的處理、只用訓練集估計。
- 找邊界情形：秩不足、全 NaN 欄位、類別順序、平手、亂數串流是否在不同方法間共用。
- 再做一次獨立的 code review：交給沒看過這份程式的審查者從頭讀，只收能重現的錯誤。

## 第 3 輪：乾淨重跑

```sh
uv sync --locked
uv run homework1/PR_HW1/pr_hw1.py --out /tmp/rerun     # 輸出到別處，不覆蓋
uv run .agents/skills/homework-max-review/scripts/compare_npz.py homework1/PR_HW1/results/results.npz /tmp/rerun/results.npz
```

結果必須逐位相同（同一台機器、同一份鎖檔）。不同就找出原因，不要只放寬容許誤差。

## 第 4 輪：數字與敘述

- 報告數字全部由建置腳本從結果檔填入；確認樣板沒有手寫數字（`grep -nE '[0-9]+\.[0-9]+' template.tex`，逐一確認是常數而非結果）。
- 每一句定性敘述（誰比較好、何時重合、在哪裡最低）都要有對應的 assert 或你親手算出的數字；做不到就改寫或刪除。
- 理論說明（例如不變性、秩的上界、隨機矩陣的特徵值範圍）用小實驗驗證一次。
- 拿 PDF 和 `results.npz` 逐句核對，找出對不上的數字和推論過頭的句子；最好也交給另一位審查者核對一次。

## 第 5 輪：圖與 PDF

- 逐頁輸出 PNG 檢視：圖例不壓到曲線、標籤不被裁切、圖在正確的節附近、首頁標題在最上方。
- 圖說只描述畫了什麼（資料、分割、重複次數、色帶意義），不放詮釋。
- `uv run .agents/skills/xelatex-cjk-report/scripts/check_pdf.py ...` 全部通過；附錄的程式就是實際執行的那份（`\lstinputlisting` 直接讀原檔）。

## 第 6 輪：文字

- `uv run .agents/skills/zh-tw-technical-writing/scripts/scan_zh_tells.py report.tex` 沒有提示，或每筆都確認過。
- 通讀一次：每段的第一句是事實、最後一句停在結果；術語前後一致；沒有與實驗無關的句子。

詳細檢查項目：`references/review-checklist.md`。
