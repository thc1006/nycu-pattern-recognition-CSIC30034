---
name: privacy-safe-commits
description: Commits and pushes work in this repo in content-based batches with plain commit messages, while keeping the student ID and other private data out of everything that leaves the machine (file contents, PDF text and metadata, file names, commit messages, history). Use before any git commit or push here, before making the repo public, and before publishing a homework PDF (分批 commit、推送、公開 repo、隱私).
---

# 保護隱私的分批 commit

## 私密資料放哪裡

- 學號只放在被忽略的 `*.local.json`，內容是 `{"student_id": "..."}`。新作業讀根目錄的 `student.local.json`，HW1 讀 `homework1/PR_HW1/student.local.json`。姓名與信箱放在公開的 `student.json`。
- 交到 e3 的 PDF 在 `homework*/submission/`，檔名含學號，整個資料夾被忽略。其他含學號的檔案也要先加進 `.gitignore` 再 commit。忽略規則裡不能寫出學號本身，要用萬用字元（例如 `homework*/**/PR_HW*_*_[0-9]*.pdf`）。
- 公開版 PDF 在 `homework*/public/PR_HW*_姓名.pdf`，由 `tools/build_report.py` 排版，排版時不放學號；繳交版在暫存資料夾排版，`report/` 裡只會有公開版。寫出兩份 PDF 之前，`build_report.py` 先檢查公開版、排版的中間檔，以及 `homeworkN/` 底下 git 會加入的檔案；只要出現任何 `*.local.json` 的值就停下，兩份 PDF 都不寫。
- 範例、測試與說明文字裡也不寫真的學號，需要時用假號碼。
- 照片、手寫推導的掃描與螢幕截圖，放進 repo 前先遮掉學號與其他不公開的資料，再用眼睛確認。圖片裡的字，`tools/scan_private.py` 讀不到。手機照片的 EXIF 可能帶有拍攝地點（GPS）與裝置資訊，眼睛看不到，掃描也不會擋；先重存成不帶中繼資料的 PNG 再加入：`uv run python -c "import sys; from PIL import Image, ImageOps; ImageOps.exif_transpose(Image.open(sys.argv[1])).save(sys.argv[2])" 原檔.jpg 新檔.png`。

## 步驟

0. 每個 clone 執行一次 `uv run tools/scan_private.py --install-hooks`，`tools/scan_private.py` 有更新之後再執行一次。hook 寫在 `.git/hooks/`，每次 `git commit` 前檢查暫存區、commit 訊息、author 與 committer，每次 push 前檢查要送出的檔案、commit、tag 與分支名稱；`git merge`、`cherry-pick`、`rebase`、`am` 做出的 commit 只在 push 前檢查。出現 `*.local.json` 裡的值、認得格式卻讀不了的檔案，或 commit 訊息不是純文字，就停下。沒有任何 `*.local.json` 時，commit 與 push 都會被擋下。新電腦上先確認 `git config user.name` 與 `git config user.email`。這個 repo 的 commit 都用 GitHub 的 noreply 信箱，換成其他信箱，那個信箱會跟著 commit 公開。
1. `git -c core.quotePath=false status --short --ignored=matching -uall`：未追蹤的檔案逐一列出，被忽略的資料夾只列一行。確認私密檔顯示為 `!!`（被忽略），並看清楚每個要加入的檔案。
2. 依內容分批，每批只 `git add` 明確的路徑，不用 `git add -A` 或 `git add .`。常見的分批順序：環境設定、課程資料、作業題目、程式、實驗結果與圖、報告與 README，最後是 skills。
3. 每批 commit 前看 `git -c core.quotePath=false diff --cached --stat`，然後執行掃描：
   ```sh
   uv run tools/scan_private.py
   ```
   它拿所有 `*.local.json` 的值，檢查暫存區的檔案、下一個 commit 的 author 與 committer，以及本機分支、tag 上遠端還沒有的一切：檔案內容與檔名、資料夾名稱、commit 訊息、author 與 committer、tag 訊息、分支與 tag 的名稱。PDF 會連同壓縮過的物件、中繼資料與附加的檔案一起讀，zip、tar、gzip 等壓縮檔與 joblib 的壓縮存檔也會讀裡面的內容。比對時忽略大小寫、空白與看不見的字元，全形數字也算。認得格式卻讀不了的檔案（加密的 PDF、7z、rar、Git LFS 指標），以及帶 trailer（例如 `Signed-off-by:`、`Change-Id:`）、emoji 或 Markdown 連結的 commit 訊息，也算問題。圖片裡的字，以及 `.mat`、HDF5、Parquet 這類格式裡壓縮過的資料，掃描讀不到，也不會擋下。
4. commit 訊息：第一行是祈使句摘要（72 字元內），需要時空一行寫原因。不加 trailer（例如 `Signed-off-by:`、`Change-Id:`）、署名、emoji 或 Markdown 連結。
5. 全部 commit 完再跑一次掃描，沒有問題才 `git push origin main`。

## 公開 repo 之前

1. 先執行 `git fetch origin --prune --tags`，再執行 `uv run tools/scan_private.py --all-history`。它檢查任何分支、tag 與遠端分支上的每一個 commit，不只還沒推送的；沒有 fetch 下來的遠端 commit 不在範圍內。
2. 用 `git ls-remote origin` 確認遠端只有要公開的分支與 tag。
3. 被 force push 蓋掉，或分支、tag 刪掉之後留下的舊 commit，不在任何分支上，前兩步看不到，公開後卻能用 SHA 打開。執行 `gh api 'repos/{owner}/{repo}/activity?per_page=100' --jq '.[] | [.activity_type, .ref, .before] | join(" ")'`，`force_push` 與 `branch_deletion` 那幾行的 SHA 要逐一確認沒有私密資料。
4. repo 的說明、網址與 topics 不在 git 裡，另外檢查：`gh repo view --json description,homepageUrl,repositoryTopics --jq '.description, .homepageUrl, (.repositoryTopics // [] | map(.name) | join(" "))' | uv run tools/scan_private.py --message /dev/stdin`。
5. 公開之後，歷史裡的每個版本都看得到，也可能已被別人複製，要拿掉只能改寫歷史並另開新的 repo。

## 出事時

- hook 擋下 commit 時，commit 還沒有建立：不該加入的檔案用 `git restore --staged <路徑>` 移出暫存區，要加入的檔案改好再 `git add`，訊息有問題就改好訊息，再重新 commit。
- 私密資料進了 commit 但還沒推送（例如裝 hook 之前就 commit 了）：用 `git log --oneline origin/main..HEAD -- <路徑>` 找出加入檔案的 commit；掃描也會印出相關的 commit 編號。
  - 只在最新的 commit：不該進版控的檔案執行 `git rm --cached <路徑>`（本機的檔案留著），內容要改的檔案改好再 `git add`，訊息有問題就改好訊息，然後執行 `git commit --amend`。學號在 author 或 committer 時，先改好 `git config user.name` 與 `git config user.email`，再執行 `git commit --amend --reset-author`。
  - 在更早的 commit：先執行 `git fetch origin`，再執行 `git reset "$(git merge-base HEAD origin/main)"`（不加 `--soft`，改動留在工作目錄、暫存區清空），改好之後照步驟 2 重新分批。推送前 `git status -sb` 顯示落後時，先執行 `git pull --rebase`。還指向舊 commit 的其他分支或 tag，用 `git branch -D` 或 `git tag -d` 刪掉，否則掃描仍會列出那些檔案。
  - 最後執行 `uv run tools/scan_private.py`。
- 已經推送：預設的 `uv run tools/scan_private.py` 只看還沒推送的部分，這時會顯示 clean；改用 `uv run tools/scan_private.py --all-history` 列出問題，用 `git log --all --oneline -- <路徑>` 找出相關的 commit，決定好怎麼處理再動手。force push 只換掉分支，舊 commit 還留在 GitHub 上，repo 公開後知道 SHA 就打得開，Activity 頁也列得出被蓋掉的 SHA。repo 還沒公開時，把改寫好的歷史推到新開的 repo，刪掉舊的，再公開新的。
