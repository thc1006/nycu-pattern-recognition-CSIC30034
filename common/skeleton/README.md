# PR HWN 程式與報告

報告的公開版（正文加程式附錄）在 `../public/`。交到 e3 的版本在 `../submission/`，只留在本機。

## 執行

所有指令都在專案根目錄執行。

```sh
uv run homeworkN/PR_HWN/check_hwN.py   # 數值檢查
uv run homeworkN/PR_HWN/pr_hwN.py      # 全部實驗與圖
uv run tools/build_report.py N         # 填入數字、排版，輸出繳交版與公開版
```

只想重畫圖：`uv run homeworkN/PR_HWN/pr_hwN.py --plots-only`。

## 檔案

| 檔案 | 內容 |
|---|---|
| `pr_hwN.py` | 實驗與作圖 |
| `check_hwN.py` | 與直接公式、SciPy、scikit-learn 對照的檢查 |
| `report_numbers.py` | 報告中的每個數字；文中的定性敘述也寫成 assert |
| `report/template.tex` | 報告內文，`<<key>>` 由 `tools/build_report.py` 填入 |
| `results/` | `results.npz`、`run_info.json`、`figures/` |
