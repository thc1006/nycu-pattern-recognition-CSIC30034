% Report class for the Pattern Recognition homework (NYCU, Fall 2026). Layout taken from HW1.
%
%   \documentclass{prhw}
%   \assignment{2}                       page header and PDF title
%   \title{...}
%   \student{name}{student ID}{email}    the ID is letters and digits; an empty ID gives the public copy.
%                                        Write it at top level; inside another macro, write \_ in the e-mail.
%   \pagelimit{5}
%   \begin{document} \maketitle ... \codeappendix ... \codefile{pr_hw2.py} \end{document}
%
% tools/build_report.py puts this folder on TEXINPUTS, fills the <<key>> placeholders and checks the page limit.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{prhw}[2026/10/13 Pattern Recognition homework report]
\LoadClass[10pt,a4paper]{article}

\RequirePackage[a4paper,hmargin=18mm,top=15mm,bottom=14mm,headheight=12pt,headsep=4mm,footskip=7mm]{geometry}
\RequirePackage{fontspec}
\RequirePackage{xeCJK}
\RequirePackage{amsmath}
\RequirePackage{unicode-math}
\RequirePackage{graphicx,booktabs,array,caption,fancyhdr,titlesec,listings,xcolor}
\RequirePackage[hidelinks]{hyperref}

% TeX Live's OTF fonts are loaded by file name. FontIndex=3 is the Traditional Chinese face of the Noto CJK collections.
\setmainfont{STIXTwoText}[Extension=.otf,UprightFont=*-Regular,BoldFont=*-Bold,ItalicFont=*-Italic,BoldItalicFont=*-BoldItalic]
\setmathfont{STIXTwoMath-Regular.otf}
\setsansfont{NotoSansCJK-Regular.ttc}[Path=/usr/share/fonts/opentype/noto/,FontIndex=3,BoldFont=NotoSansCJK-Bold.ttc,BoldFeatures={FontIndex=3}]
\setmonofont{Inconsolatazi4}[Extension=.otf,UprightFont=*-Regular,BoldFont=*-Bold,Scale=MatchLowercase]
\setCJKmainfont{NotoSerifCJK-Regular.ttc}[Path=/usr/share/fonts/opentype/noto/,FontIndex=3,BoldFont=NotoSerifCJK-Bold.ttc,BoldFeatures={FontIndex=3}]
\setCJKsansfont{NotoSansCJK-Regular.ttc}[Path=/usr/share/fonts/opentype/noto/,FontIndex=3,BoldFont=NotoSansCJK-Bold.ttc,BoldFeatures={FontIndex=3}]
\setCJKmonofont{NotoSansCJK-Regular.ttc}[Path=/usr/share/fonts/opentype/noto/,FontIndex=8]
% A character missing from its font stops the build: Greek letters and math symbols such as √ ≤ ≥ in code listings
% (Inconsolata has none), or arrows and relations such as → ≤ ≈ ∞ in prose (STIX Two Text has none; write $\to$,
% $\le$, $\approx$, $\infty$).
\tracinglostchars=3
\catcode"200B=9 \catcode"2060=9 \catcode"FEFF=9 % zero-width characters are dropped on input

\linespread{1.25}
\setlength{\parindent}{2em}
\setlength{\parskip}{1pt}
\titleformat{\section}{\sffamily\bfseries\normalsize}{\thesection}{0.8em}{}
\titlespacing*{\section}{0pt}{5pt}{2pt}
\titleformat{\subsection}{\sffamily\bfseries\small}{}{0pt}{}
\titlespacing*{\subsection}{0pt}{6pt}{2pt}
\captionsetup{font=small,labelfont=bf,labelsep=quad,singlelinecheck=false,skip=3pt}
\captionsetup[figure]{name=圖}
\captionsetup[table]{name=表,position=top}
\setlength{\textfloatsep}{7pt plus 2pt minus 2pt}
\setlength{\floatsep}{6pt plus 2pt minus 2pt}
\setlength{\abovedisplayskip}{3pt}
\setlength{\belowdisplayskip}{3pt}
\renewcommand{\arraystretch}{1.05}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small Pattern Recognition, NYCU Fall 2026}
\newcommand*{\prhw@righthead}{Assignment \#\prhw@number}
\fancyhead[R]{\small\prhw@righthead}
\fancyfoot[C]{\small\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\lstset{language=Python,basicstyle=\ttfamily\fontsize{7.3}{8.7}\selectfont,numbers=left,numberstyle=\tiny\color{gray},
  numbersep=6pt,xleftmargin=1.6em,breaklines=true,breakatwhitespace=false,columns=fullflexible,keepspaces=true,
  showstringspaces=false,commentstyle=\color{black!60},keywordstyle=\bfseries,upquote=true,aboveskip=4pt}

\newcommand*{\prhw@number}{}
\newcommand*{\prhw@name}{}
\newcommand*{\prhw@id}{}
\newcommand*{\prhw@email}{}
\newcommand*{\prhw@pagelimit}{5}

\newcommand*{\assignment}[1]{%
  \renewcommand*{\prhw@number}{#1}%
  \hypersetup{pdftitle={Pattern Recognition Assignment #1}}}
\newcommand*{\student}[2]{%
  \renewcommand*{\prhw@name}{#1}%
  \edef\prhw@id{\zap@space#2 \@empty}%
  \ifx\prhw@id\@empty\hypersetup{pdfauthor={#1}}\else\hypersetup{pdfauthor={#1 \prhw@id}}\fi
  \begingroup\catcode`\_=12 \prhw@setemail}
% The e-mail is read with _ as an ordinary character, so first_last and first\_last both print one underscore.
\newcommand*{\prhw@setemail}[1]{\endgroup\renewcommand*{\prhw@email}{#1}}
\newcommand*{\pagelimit}[1]{\renewcommand*{\prhw@pagelimit}{#1}}
\AtBeginDocument{%
  \ifx\prhw@number\@empty\ClassError{prhw}{Missing \string\assignment}{Put \string\assignment{N} in the preamble.}\fi
  \ifx\prhw@name\@empty\ClassError{prhw}{Missing \string\student}{Put \string\student{name}{ID}{email} in the preamble.}\fi}

\newif\ifprhw@titled
\AtEndDocument{\ifprhw@titled\else\ClassError{prhw}{Missing \string\maketitle}{Put \string\maketitle\space right after \string\begin{document}.}\fi}
\renewcommand*{\maketitle}{%
  \ifprhw@titled\ClassError{prhw}{\string\maketitle\space used twice}{Call it once, right after \string\begin{document}.}\fi
  \@tempswafalse
  \ifhmode\@tempswatrue\fi
  \ifdim\pagetotal>\z@\@tempswatrue\fi
  \ifnum\c@page>\@ne\@tempswatrue\fi
  \if@tempswa\ClassError{prhw}{\string\maketitle\space is not at the top of page 1}{Put \string\maketitle\space right after \string\begin{document}.}\fi
  \global\prhw@titledtrue
  \noindent{\sffamily\bfseries\large\@title}\par
  \vspace{1pt}
  \noindent{\small\mbox{\prhw@name}\ifx\prhw@id\@empty\else\quad\mbox{\prhw@id}\fi\quad\mbox{\prhw@email}}%
  {\rightskip=0pt plus 1fil\relax\par}% a long name line wraps instead of running into the margin
  \vspace{2pt}
  \suppressfloats[t]}

\newcommand*{\fig}[1]{\includegraphics[width=\linewidth]{../results/figures/#1.pdf}}

% Ends the body on a fresh page. Floats still pending are flushed first, so they count toward the body.
% Label prhw@body-end carries the page limit as its \ref and the number of body pages shipped as its \pageref
% (\ReadonlyShipoutCounter, so \pagenumbering cannot shorten it); the reserved name keeps it apart from author labels.
\newif\ifprhw@appendix
\AtEndDocument{\ifprhw@appendix\else\ClassError{prhw}{Missing \string\codeappendix}{End the body with \string\codeappendix.}\fi}
\newcommand*{\codeappendix}{%
  \ifprhw@appendix\ClassError{prhw}{\string\codeappendix\space used twice}{Call it once, after the body.}\fi
  \clearpage
  \global\prhw@appendixtrue
  \immediate\write\@auxout{\string\newlabel{prhw@body-end}{{\prhw@pagelimit}{\the\ReadonlyShipoutCounter}{}{}{}}}%
  \gdef\prhw@righthead{附錄　程式碼（不計入 \prhw@pagelimit\space 頁）}%
  \fancyhead[R]{\small\prhw@righthead}%
  \section*{附錄　程式碼}%
  \global\let\section\prhw@nosection}
\newcommand*{\prhw@nosection}{\ClassError{prhw}{\string\section\space after \string\codeappendix}{Body text goes before \string\codeappendix; the appendix holds the program listing.}}
\newif\ifprhw@code
\AtEndDocument{\ifprhw@appendix\ifprhw@code\else\ClassError{prhw}{No \string\codefile\space after \string\codeappendix}{List the program with \string\codefile.}\fi\fi}
\newcommand*{\codefile}[1]{%
  \ifprhw@appendix\else\ClassError{prhw}{\string\codefile\space before \string\codeappendix}{Code listings go in the appendix, after \string\codeappendix.}\fi
  \global\prhw@codetrue
  \subsection*{\detokenize{#1}}\lstinputlisting{../#1}}
