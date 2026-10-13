"""Flag formulaic phrasing, punctuation habits and mainland terms in Traditional Chinese text.

Usage (repository root):  uv run tools/scan_zh_style.py FILE [FILE ...]

Works on .tex, .md and .txt. In .tex files, code (\\verb, \\Verb, \\lstinline, \\mintinline and the verbatim,
Verbatim, lstlisting and minted environments), URLs (\\url, \\href, \\path, \\nolinkurl), math ($…$, $$…$$, \\(…\\),
\\[…\\] and environments such as align), LaTeX comments and command names are stripped first; line numbers still
match the file.
Every hit is a prompt to reread the sentence, not an automatic error.
"""
import re
import sys
from pathlib import Path

CJK = r"\u4e00-\u9fff"
CLAUSE = r"[^。！？；\n]{0,30}"

CHECKS = {
    "翻案句": [rf"不是{CLAUSE}而是", rf"並非{CLAUSE}而是", rf"與其說{CLAUSE}不如說", r"不只是",
             rf"不僅{CLAUSE}(更|還|也)", rf"不是{CLAUSE}，是", r"，不是", r"而非", r"而不是"],
    "防禦性否定": [r"並不(表示|代表|意味)", r"不代表", r"不能(把|當作|當成|說成|視為)", r"冒稱", r"沒有偷偷", r"不要誤"],
    "路標詞": [r"值得(注意|一提)的是", r"需要(指出|注意)的是", r"更重要的是", r"關鍵在於", r"重要的是"],
    "套話與複述": [r"這意味著", r"換句話說", r"由此可見", r"綜上所述", r"總的來說", r"總而言之", r"總結來說",
              r"簡而言之", r"隨著.{0,15}(發展|進步|普及)", r"在.{0,20}的背景下", r"讓我們", r"以下是",
              r"本(文|報告)將"],
    "誇飾與黑話": [r"至關重要", r"不可或缺", r"意義重大", r"深入探討", r"深度剖析", r"全方位", r"多維度", r"無縫",
              r"賦能", r"助力", r"打造", r"抓手", r"閉環", r"底層邏輯", r"顆粒度", r"旨在", r"致力於", r"引領",
              r"顯著", r"扮演.{0,10}角色", r"充分(證明|說明|展現)"],
    "翻譯腔": [r"進行.{0,6}(處理|分析|操作|計算|比較)", r"作為一(種|個)", r"通過.{0,15}來", r"對於.{0,15}(來說|而言)",
            r"被.{0,10}所"],
    "順序詞起句": [r"(^|[。！？])(首先|其次|再者|最後)，"],
    "標點": [r"——", r"—", r"→", r"⇒", r"[“”]", rf'"(?=[{CJK}])', rf'(?<=[{CJK}])"', r"！"],
    "兩岸用語": [r"數據", r"信息", r"質量", r"默認", r"優化", r"運行", r"算法", r"方差", r"協方差", r"魯棒",
              r"歸一化", r"偽逆", r"本征", r"噪聲", r"視頻", r"軟件", r"代碼", r"打印", r"網絡", r"(?<![多少倍])數組",
              r"變量", r"圖像", r"採樣", r"概率", r"正態", r"均值", r"似然", r"樣本量", r"模式識別",
              r"回歸", r"通過", r"文件"],
}


MATH_ENV = r"equation|align|alignat|gather|multline|flalign|eqnarray|displaymath|math"
CODE_ENV = r"verbatim|Verbatim|BVerbatim|LVerbatim|lstlisting|minted"
# One left-to-right pass over code, URLs, line breaks and comments: whichever starts first wins, so a comment that
# mentions \begin{verbatim} stays a comment and a % or $ inside code stays code. Only code environments cross lines.
FIRST = re.compile(
    rf"(?P<env>\\begin\{{({CODE_ENV})(\*?)\}}(?s:.*?)\\end\{{\2\3\}})"
    r"|\\lstinline(?:\[[^]\n]*\])?\{[^}\n]*\}"
    r"|\\mintinline(?:\[[^]\n]*\])?\{[^}\n]*\}(?:\{[^}\n]*\}|(?P<md>[^\w\s{])[^\n]*?(?P=md))"
    r"|\\(?:verb|Verb|lstinline)\*?(?:\[[^]\n]*\])?(?P<d>[^\w\s{])[^\n]*?(?P=d)"
    r"|\\(?:url|href|nolinkurl|path)\{(?:[^{}\n]|\{[^{}\n]*\})*\}"
    r"|\\\\(?:\[[^]\n]*\])?"  # a line break, so \\[2pt], \\$ and \\% are not misread
    r"|(?P<pct>\\%)"
    r"|%[^\n]*")


def blank(m):
    """A removed span keeps its line breaks, so the reported line numbers stay right."""
    return " " + "\n" * m.group().count("\n")


def first_pass(m):
    if m.group("pct"):
        return m.group()  # an escaped percent is text
    return blank(m) if m.group("env") else " "


def strip_latex(text):
    text = FIRST.sub(first_pass, text)
    text = re.sub(rf"\\begin\{{({MATH_ENV})(\*?)\}}.*?\\end\{{\1\2\}}", blank, text, flags=re.S)
    for math in (r"\$\$.*?\$\$", r"\\\[.*?\\\]", r"\\\(.*?\\\)", r"(?<!\\)\$[^$]*\$"):
        text = re.sub(math, blank, text, flags=re.S)
    text = re.sub(r"\\(begin|end)\{[^}\n]*\}(\[[^]\n]*\])?", " ", text)
    text = re.sub(r"\\[a-zA-Z@]+\*?", " ", text)
    return text


def scan(path):
    raw = Path(path).read_text(encoding="utf-8")
    text = strip_latex(raw) if path.endswith(".tex") else raw
    lines = text.splitlines()
    hits = 0
    for category, patterns in CHECKS.items():
        for pattern in patterns:
            for n, line in enumerate(lines, 1):
                for m in re.finditer(pattern, line):
                    s = max(m.start() - 12, 0)
                    print(f"{path}:{n}: [{category}] {m.group(0)!r}  …{line[s:m.end() + 12].strip()}…")
                    hits += 1
    for n, line in enumerate(lines, 1):
        for sentence in re.split(r"[。！？]", line):
            words = len(re.findall(rf"[{CJK}]、(?=[{CJK}])", sentence))  # lists of words, not of numbers
            if words >= 3:
                print(f"{path}:{n}: [頓號長串] {words} 個詞語頓號  …{sentence.strip()[:40]}…")
                hits += 1
    body = "".join(ch for ch in text if re.match(rf"[{CJK}]", ch))
    per_k = lambda ch: 1000 * text.count(ch) / max(len(body), 1)
    print(f"{path}: {len(body)} 個漢字；冒號 {per_k('：'):.1f}、分號 {per_k('；'):.1f}、括號 {per_k('（'):.1f} 個/千字；"
          f"粗體 {raw.count(chr(92) + 'textbf') + raw.count('**')} 處；共 {hits} 筆提示")
    return hits


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        scan(p)
