---
name: privacy-safe-commits
description: Commits and pushes work in this repo in content-based batches with plain commit messages, while keeping the student ID and other private data out of everything that leaves the machine (file contents, PDF text and metadata, file names, commit messages, history). Use before any git commit or push here, and when asked to 分批 commit、推上去、把 repo 公開、開源但保護隱私, or to publish a homework PDF.
---

# 保護隱私的分批 commit

## 私密資料放哪裡

- 學號只放在被忽略的 `*.local.json`，內容是 `{"student_id": "..."}`。新作業讀根目錄的 `student.local.json`，HW1 讀 `homework1/PR_HW1/student.local.json`。姓名與信箱放在公開的 `student.json`。
- 交到 e3 的 PDF 在 `homework*/submission/`，檔名含學號，整個資料夾被忽略。其他含學號的檔案也要先加進 `.gitignore` 再 commit。忽略規則裡不能寫出學號本身，要用萬用字元（例如 `homework*/**/PR_HW*_*_[0-9]*.pdf`）。
- 公開版 PDF 在 `homework*/public/PR_HW*_姓名.pdf`，由 `tools/build_report.py` 排版，排版時不放學號。寫出兩份 PDF 之前，它先檢查公開版、排版的中間檔，以及 `homeworkN/` 底下 git 會加入的檔案；只要出現任何 `*.local.json` 的值就停下，兩份 PDF 都不寫。
- 範例、測試與說明文字裡也不寫真的學號，需要時用假號碼。

## 步驟

1. `git status --short --ignored=matching -uall`：未追蹤的檔案逐一列出，被忽略的資料夾只列一行，不會印出 `submission/` 裡含學號的檔名。確認私密檔顯示為 `!!`（被忽略），並看清楚每個要加入的檔案。
2. 依內容分批，每批只 `git add` 明確的路徑，不用 `git add -A` 或 `git add .`。常見的分批順序：環境設定、課程資料、作業題目、程式、實驗結果與圖、報告與 README，最後是 skills。
3. 每批 commit 前看 `git diff --cached --stat`，然後執行掃描：
   ```sh
   uv run tools/scan_private.py
   ```
   它拿所有 `*.local.json` 的值，檢查暫存區的檔案（內容、檔名，PDF 連同壓縮過的物件與中繼資料）和每個尚未推送的 commit（檔案、訊息、author 與 committer）。比對時忽略大小寫與空白，全形數字也算。
4. commit 訊息：第一行是祈使句摘要（72 字元內），需要時空一行寫原因。不加 trailer（例如 `Co-authored-by`）、署名、工具名稱或 emoji。
5. 全部 commit 完再跑一次掃描，沒有問題才 `git push origin main`。tag 要另外推（`git push origin hwN`），tag 的訊息也不寫學號。

## 出事時

- 私密資料進了 commit 但還沒推送：用 `git commit --amend`，或 `git reset --soft <base>` 後重新分批，再掃描一次。
- 已經推送：不要直接 force push 或改寫遠端歷史。先列出受影響的 commit 與檔案，確認處理方式之後再動手。
