---
name: uv-locked-python
description: Runs and manages Python in this repository through uv with exact version pins kept at the repo root (pyproject.toml, uv.lock, .python-version). Use whenever running a Python script, adding or upgrading a package, or writing run instructions in this repo, including requests like 用 uv 跑、加套件、鎖版本. Never use pip, python -m venv or requirements.txt here.
---

# uv 鎖定的 Python 環境

根目錄的三個檔案決定環境：

- `.python-version`：直譯器版本，精確到 patch。
- `pyproject.toml`：直接相依套件，全部 `==` 固定；`requires-python` 鎖在單一 minor 版本。
- `uv.lock`：所有遞移相依的版本與雜湊，要一起 commit。

## 指令（都在專案根目錄執行）

| 目的 | 指令 |
|---|---|
| 執行腳本 | `uv run path/to/script.py` |
| 臨時多一個套件、不寫進專案 | `uv run --with pkg==X.Y python ...` |
| 新增套件 | `uv add --bounds exact pkg`，再 commit `pyproject.toml` 與 `uv.lock` |
| 升級單一套件 | `uv lock --upgrade-package pkg && uv sync --locked` |
| 依鎖檔重建環境 | `uv sync --locked` |
| 不安裝就用 CLI 工具 | `uvx --from tool==X.Y cmd` |

## 規則

- 子資料夾的腳本也從根目錄用 `uv run` 執行，才會用到同一個環境。腳本內以 `Path(__file__)` 找資料，不依賴工作目錄。
- README 與報告中的執行說明寫 `uv run ...`，不寫 `pip install` 或 `python -m venv`。
- 換套件版本後，數值結果可能改變：重跑實驗，並確認輸出的版本紀錄（例如 `results/run_info.json`）已更新。
- 平行計算時把 BLAS 執行緒設為 1（在 import numpy 之前設 `OPENBLAS_NUM_THREADS` 等環境變數），由 process pool 負責平行，結果才穩定。
