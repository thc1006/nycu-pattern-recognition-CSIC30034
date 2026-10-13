---
name: zh-tw-technical-writing
description: Writes and revises Traditional Chinese (Taiwan) technical text, such as homework reports and READMEs, in a plain, factual style with Taiwan terminology. Use when drafting or editing 繁體中文報告、作業、說明文件, or when asked to 潤稿、寫得平實、少套話、改成台灣用語. The scanner tools/scan_zh_style.py flags formulaic phrasing, punctuation habits and mainland terms.
---

# 繁體中文技術寫作

目標：平實、有根據。只寫做了什麼、得到什麼數字、為什麼。

## 寫之前

- 先把每個要寫的數字從程式輸出算出來，不手抄。報告數字用樣板填入（見 `pr-homework-workflow`）。
- 先查證再寫：每個「因為」都要有實驗或推導支撐；查不到就不寫，不用模糊語氣帶過。

## 規則

1. 不寫翻案句：「不是…而是」「並非」「而非」「而不是」「，不是 X」「不僅…更」。直接寫正面事實。
2. 不寫防禦性否定：「不能把…當作」「並不表示」「沒有偷偷…」。限制寫成具體條件與數字。
3. 刪路標詞與套話：值得注意的是、需要指出的是、更重要的是、關鍵在於、這意味著、換句話說、由此可見、綜上所述、總而言之、本報告將。
4. 不用黑話與誇飾：至關重要、不可或缺、深入探討、全方位、賦能、打造、旨在。「顯著」只用在做過檢定的結果。
5. 每個結論附數字與條件，例如「q = 100 時從 93.9% 降到 83.2%（20 次平均）」。
6. 段落結尾停在最後一個具體結果，不加總結句或金句。
7. 不用三連排比與相鄰句同骨架；三個並列情況改寫成不同句型。
8. 標題照作業題號，短而平實；不用「X：Y」式標題、粗體、emoji、條列論證。
9. 冒號只用在公式、表格或定義前；分號少用，能斷句就用句號。
10. 不用破折號、箭頭；中文用全形標點與「」引號，不替普通詞加引號。
11. 同一概念全文只用一個詞，第一次出現附英文（例：擬反矩陣（pseudo-inverse））。
12. 改翻譯腔：對…進行、作為一種、通過…來、對於…來說、被…所。
13. 用台灣用語（`references/terms.md`），例如資料、變異數、共變異數矩陣、擬反矩陣、雜訊、程式。
14. 適度用第一人稱交代自己的選擇與預期：「我原本以為…，結果…，原因是…」。
15. 寫完通讀一次，刪掉不影響理解的句子。

完整清單與改寫範例：`references/checklist.md`。

## 掃描

```sh
uv run tools/scan_zh_style.py homeworkN/PR_HWN/report/template.tex
```

每一筆提示都要回頭讀原句再決定改不改；數字列表的頓號，以及 `.tex` 裡數學式（`$…$`、`\[…\]`、`align` 等環境）的符號已排除。輸出最後一行列出冒號、分號、括號的密度（每千字）與粗體數，冒號與分號大約各在 3 以下比較自然。
