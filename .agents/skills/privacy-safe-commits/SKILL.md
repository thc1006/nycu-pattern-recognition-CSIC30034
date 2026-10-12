---
name: privacy-safe-commits
description: Commits and pushes work in this repo in content-based batches with plain commit messages, while keeping the student ID and other private data out of everything that leaves the machine (file contents, PDF text and metadata, file names, commit messages, history). Use before any git commit or push here, and when asked to 分批 commit、推上去、開源但保護隱私, or to publish a homework PDF.
---

# 保護隱私的分批 commit

## 私密資料放哪裡

- 學號只放在被忽略的 `*.local.json`，例如 `homework1/PR_HW1/student.local.json`：`{"student_id": "..."}`。
- 交到 e3 的 PDF 在 `homework*/submission/`，檔名含學號，整個資料夾被忽略。其他含學號的檔案也要先加進 `.gitignore` 再 commit。忽略規則裡不能寫出學號本身，要用萬用字元（例如 `homework*/**/PR_HW*_*_[0-9]*.pdf`）。
- 公開版 PDF 在 `homework*/public/PR_HW*_姓名.pdf`，由建置腳本在沒有學號的情況下產生，並檢查文字、中繼資料與原始位元組。

## 步驟

1. `git status --short --ignored`：確認私密檔顯示為 `!!`（被忽略）。
2. 依內容分批，每批只 `git add` 明確的路徑，不用 `git add -A` 或 `git add .`。常見的分批順序：環境設定、課程資料、作業題目、程式、實驗結果與圖、報告與 README，最後是 skills。
3. 每批 commit 前看 `git diff --cached --stat`，然後執行掃描：
   ```sh
   uv run .agents/skills/privacy-safe-commits/scripts/scan_private.py
   ```
4. commit 訊息：第一行是祈使句摘要（72 字元內），需要時空一行寫原因。不加 `Co-Authored-By`、`Generated with`、工具名稱或 emoji。
5. 全部 commit 完再跑一次掃描（會檢查所有尚未推送的 commit，包括其中每個 PDF），通過才 `git push origin main`。

## 出事時

- 私密資料進了 commit 但還沒推送：用 `git commit --amend`，或 `git reset --soft <base>` 後重新分批，再掃描一次。
- 已經推送：先停下來回報，不要自己 force push 或改寫遠端歷史。
