---
name: pr-homework-workflow
description: End-to-end workflow for the NYCU Pattern Recognition homework in this repo. Turns the assignment transcription into a requirement checklist, implements the methods in NumPy under uv, runs seeded repeated experiments, draws figures, and builds the submission PDF (report within the page limit plus a code appendix) whose numbers are filled from saved results. Use when starting, continuing or finishing a homeworkN assignment, or when asked to 實作作業、寫報告、產生繳交 PDF.
---

# 圖形識別作業流程

完整範例：`homework1/PR_HW1/`（程式、結果、樣板、建置腳本都在那裡）。

## 1. 讀題

- 讀 `homeworkN/PR_HWN_full_transcription.md`（題目全文）。姓名與信箱照 HW1 報告首頁寫。
- 讀相關的講義頁（`material/pdf/`；本機另有逐頁文字版 `material/PR_Set0*.md`，不進版控），記下老師的定義與記號（例如 MD 分類器用各類共變異數、`S_w=ΣP_iΣ_i`、ridge 寫成 `Σ+γI`）。
- 把每一句要求拆成一列清單：要求、我的做法、輸出的圖或數字。最後審查時逐列打勾。

## 2. 實作

- 環境照 `uv-locked-python`；核心估計只用 NumPy，scikit-learn 只載資料或拿來對照。
- 所有平均數、共變異數、標準化、PCA、LDA 只用訓練集估計。
- 固定種子並重複（例如 20 次），每次重抽資料與分割；同一次重複內各方法共用同一個分割，比較才是成對的。
- 遇到奇異矩陣要在報告中講清楚處理方式（擬反矩陣、ridge、限制維度），並在圖上標出奇異區。
- 另寫 `check_hwN.py`，把每個估計器和直接公式、SciPy、scikit-learn 比對。
- 結果存成 `results/results.npz`（陣列前兩維為分割與重複）與 `run_info.json`（種子、網格、版本、耗時）。

## 3. 報告

- 樣板 `report/template.tex` 中的數字一律寫成 `<<key>>`，由 `build_report.py` 從 `results.npz` 計算後填入；樣板缺值或多值都要報錯。
- 文中的定性敘述（「A 在每個 σ² 都低於 B」「曲線在可逆區完全重合」）同時寫成 `build_report.py` 裡的 assert，資料一變就會失敗。
- 每題一節，節名寫題號；每節依序寫結果、預期、原因。文字規範照 `zh-tw-technical-writing`。
- 排版與頁數檢查照 `xelatex-cjk-report`；正文結尾放 `\label{body-end}`，附錄用 `\lstinputlisting` 放入實際執行的 `.py`。
- 學號只放在被 git 忽略的 `homeworkN/PR_HWN/student.local.json`。建置腳本產出兩份：`homeworkN/submission/PR_HWN_姓名_學號.pdf` 交 e3，不進版控；`homeworkN/public/PR_HWN_姓名.pdf` 推上 GitHub，內文、中繼資料、檔名都沒有學號，並由腳本自動檢查。

## 4. 交件前

照 `homework-max-review` 做完整審查，至少包含乾淨環境重跑、數字逐一比對與需求清單打勾。之後照 `privacy-safe-commits` 分批 commit 與推送。
