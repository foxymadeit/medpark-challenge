% medpark-mom.cls: Minutes of Meeting for Medpark International Hospital.
% XeLaTeX only. Fonts ship in ./fonts (OFL), so it compiles with no network.
%
% The generator fills the header fields (\mom...{} setters, from checked facts).
% The language model writes only the body, using the commands in section 5.
% Anything else in the body is rejected by mom/latexcheck.py before compiling.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{medpark-mom}[2026/09/26 Medpark minutes]
\providecommand\momtemplatedir{./}
\PassOptionsToPackage{table}{xcolor}
\LoadClass[11pt,a4paper]{article}

% ---------------------------------------------------------------- 1. packages
\RequirePackage{iftex}
\RequireXeTeX
\RequirePackage[a-2b]{pdfx}          % PDF/A-2b archival; metadata from \jobname.xmpdata
\RequirePackage{fontspec}
\RequirePackage{polyglossia}
\RequirePackage[margin=21mm,top=30mm,bottom=24mm,headheight=16mm,headsep=8mm,footskip=11mm]{geometry}
\RequirePackage{xcolor}
\RequirePackage{graphicx}
\RequirePackage{fancyhdr}
\RequirePackage{lastpage}
\RequirePackage{xltabular}
\RequirePackage{colortbl}
\RequirePackage{array}
\RequirePackage{enumitem}
\RequirePackage{titlesec}
\RequirePackage{microtype}
\RequirePackage{ragged2e}
\RequirePackage{needspace}
\hypersetup{hidelinks}

% ---------------------------------------------------------------- 2. brand
\definecolor{mpteal}{HTML}{008286}
\definecolor{mpgold}{HTML}{DAB027}
\definecolor{mpyellow}{HTML}{F5EA61}
\definecolor{mpslate}{HTML}{515963}
\definecolor{mpcharcoal}{HTML}{403E3D}
\definecolor{mprow}{HTML}{F2F6F6}

\defaultfontfeatures{Ligatures=TeX}
\setmainfont{PT_Serif-Web}[Path=\momtemplatedir fonts/, Extension=.ttf,
  UprightFont=*-Regular, BoldFont=*-Bold, ItalicFont=*-Italic, BoldItalicFont=*-BoldItalic]
\newfontfamily\momsans{Montserrat}[Path=\momtemplatedir fonts/, Extension=.ttf,
  UprightFont=*-Regular, BoldFont=*-SemiBold, FontFace={m}{n}{*-Medium}]
\newcommand\momlabel{\momsans\fontseries{m}\selectfont}
\color{mpcharcoal}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.4em}
\linespread{1.08}
\AtBeginDocument{\RaggedRight}  % no Romanian/Russian hyphenation needed; reads well in every language

% ---------------------------------------------------------------- 3. language
% \momlanguage{ro|ru|en} sets hyphenation and every fixed label.
\ExplSyntaxOn
\cs_generate_variant:Nn \prop_item:Nn {Ne}
\cs_generate_variant:Nn \seq_gput_right:Nn {Ne}
\prop_new:N \g_mom_strings_prop
\cs_new_protected:Npn \mom_str:nnnn #1#2#3#4
  { \prop_gput:Nnn \g_mom_strings_prop {ro/#1} {#2}
    \prop_gput:Nnn \g_mom_strings_prop {ru/#1} {#3}
    \prop_gput:Nnn \g_mom_strings_prop {en/#1} {#4} }
\tl_new:N \g_mom_lang_tl
\NewDocumentCommand \momstr { m } { \prop_item:Ne \g_mom_strings_prop { \g_mom_lang_tl / #1 } }
\NewDocumentCommand \momlanguage { m }
  { \tl_gset:Nn \g_mom_lang_tl {#1}
    \str_case:nn {#1}
      { {ro} { \setdefaultlanguage{romanian} }
        {ru} { \setdefaultlanguage{russian} \setotherlanguage{english} }
        {en} { \setdefaultlanguage[variant=british]{english} } } }
\NewDocumentCommand \momdefstring { m m m m } { \mom_str:nnnn {#1} {#2} {#3} {#4} }
\ExplSyntaxOff
\momdefstring {doc}       {PROCES-VERBAL}                {ПРОТОКОЛ}                    {MINUTES}
\momdefstring {no}        {nr.}                          {№}                           {No.}
\momdefstring {date}      {Data}                         {Дата}                        {Date}
\momdefstring {time}      {Ora}                          {Время}                       {Time}
\momdefstring {place}     {Locul}                        {Место}                       {Place}
\momdefstring {chair}     {Președinte de ședință}        {Председатель}                {Chair}
\momdefstring {secretary} {Secretar}                     {Секретарь}                   {Secretary}
\momdefstring {present}   {Au participat}                {Присутствовали}              {Present}
\momdefstring {apologies} {Absenți motivat}              {Отсутствовали}               {Apologies}
\momdefstring {summary}   {Rezumat}                      {Краткое содержание}          {Summary}
\momdefstring {agenda}    {Ordinea de zi}                {Повестка заседания}          {Agenda}
\momdefstring {decisions} {Hotărâri}                     {Решения}                     {Decisions}
\momdefstring {decision}  {Hotărârea}                    {Решение}                     {Decision}
\momdefstring {actions}   {Plan de acțiuni}              {План действий}               {Action log}
\momdefstring {task}      {Acțiunea}                     {Поручение}                   {Action}
\momdefstring {owner}     {Responsabil}                  {Ответственный}               {Owner}
\momdefstring {deadline}  {Termen}                       {Срок}                        {Due}
\momdefstring {vote}      {Vot}                          {Голосование}                 {Vote}
\momdefstring {next}      {Următoarea ședință}           {Следующее заседание}         {Next meeting}
\momdefstring {signature} {Semnătura}                    {Подпись}                     {Signature}
\momdefstring {aifooter}  {Generat local de AI (\momvalue{model}); verificat de președinte înainte de trimitere.}
                          {Составлено локально ИИ (\momvalue{model}); проверено председателем перед отправкой.}
                          {Drafted locally by AI (\momvalue{model}); reviewed by the chair before sending.}
\momdefstring {page}      {Pagina}                       {Страница}                    {Page}
\momdefstring {of}        {din}                          {из}                          {of}

\ExplSyntaxOn
% ---------------------------------------------------------------- 4. header fields
% Set by the generator from checked facts: \momset{key}{value}. A field that was
% not given is not set at all, and \momhas leaves out everything that shows it.
\prop_new:N \g_mom_values_prop
\NewDocumentCommand \momset { m m } { \prop_gput:Nnn \g_mom_values_prop {#1} {#2} }
\NewDocumentCommand \momvalue { m } { \prop_item:Nn \g_mom_values_prop {#1} }
\NewExpandableDocumentCommand \momhas { m +m +m }
  { \prop_if_in:NnTF \g_mom_values_prop {#1} {#2} {#3} }

% decisions and actions are collected where the model writes them, printed as tables
\seq_new:N \g_mom_decisions_seq
\seq_new:N \g_mom_actions_seq
\int_new:N \g_mom_decision_int
\int_new:N \g_mom_action_int
\cs_new_protected:Npn \mom_add_decision:nnn #1#2#3
  { \int_gincr:N \g_mom_decision_int
    \seq_gput_right:Ne \g_mom_decisions_seq
      { \int_use:N \g_mom_decision_int
        \exp_not:n { & #2 \tl_if_blank:nF {#3} { \enspace{\color{mpslate}\small(#3)} } \\ } } }
% the owner and deadline columns are printed only when some action has one
\bool_new:N \g_mom_owners_bool
\bool_new:N \g_mom_deadlines_bool
\tl_new:N \g_mom_action_rows_tl
\cs_new_protected:Npn \mom_add_action:nnnn #1#2#3#4
  { \int_gincr:N \g_mom_action_int
    \tl_if_blank:nF {#2} { \bool_gset_true:N \g_mom_owners_bool }
    \tl_if_blank:nF {#3} { \bool_gset_true:N \g_mom_deadlines_bool }
    \seq_gput_right:Ne \g_mom_actions_seq { { \int_use:N \g_mom_action_int } \exp_not:n { {#4} {#2} {#3} } } }
\cs_new:Npn \mom_action_row:n #1 { \mom_action_row:nnnn #1 }
\cs_new:Npn \mom_action_row:nnnn #1#2#3#4
  { \exp_not:n { #1 & #2 }
    \bool_if:NT \g_mom_owners_bool { \exp_not:n { & #3 } }
    \bool_if:NT \g_mom_deadlines_bool { \exp_not:n { & #4 } } \exp_not:N \\ }
\NewDocumentCommand \mom@actioncolumns {}   % O and W: the owner and deadline columns, or nothing
  { \bool_if:NTF \g_mom_owners_bool { \newcolumntype{O}{>{\raggedright\arraybackslash}p{38mm}} } { \newcolumntype{O}{} }
    \bool_if:NTF \g_mom_deadlines_bool { \newcolumntype{W}{>{\raggedright\arraybackslash}p{26mm}} } { \newcolumntype{W}{} }
    \tl_gset:Ne \g_mom_action_rows_tl { \seq_map_function:NN \g_mom_actions_seq \mom_action_row:n } }
\NewExpandableDocumentCommand \mom@ifowners { +m } { \bool_if:NT \g_mom_owners_bool {#1} }
\NewExpandableDocumentCommand \mom@ifdeadlines { +m } { \bool_if:NT \g_mom_deadlines_bool {#1} }
\NewDocumentCommand \mom@decisionrows {} { \seq_use:Nn \g_mom_decisions_seq {} }
\NewDocumentCommand \mom@actionrows {} { \tl_use:N \g_mom_action_rows_tl }
\NewExpandableDocumentCommand \mom@ifdecisions { +m } { \int_compare:nNnT \g_mom_decision_int > 0 {#1} }
\NewExpandableDocumentCommand \mom@ifactions { +m } { \int_compare:nNnT \g_mom_action_int > 0 {#1} }

% ---------------------------------------------------------------- 5. body commands (the model's vocabulary)
% Every fact command carries the ID of a checked fact (D1, A2, N3, T1, C1).
\NewDocumentCommand \topic { m m }        % {T1}{Title of the agenda item}
  { \section{#2} }
\NewDocumentCommand \presented { m m m }  % {N1}{who}{what they presented or said, reported speech}
  { \par #3 \par }
\NewDocumentCommand \noted { m m }        % {N2}{what the meeting noted}
  { \par #2 \par }
\NewDocumentCommand \decision { m m m }   % {D1}{decision text}{vote, or empty}
  { \mom_add_decision:nnn {#1} {#2} {#3}
    \mom_item:nn { \momstr{decision}~\int_use:N \g_mom_decision_int }
      { #2 \tl_if_blank:nF {#3} { \enspace{\color{mpslate}\small(#3)} } } }
\NewDocumentCommand \action { m m m m }   % {A1}{owner}{deadline or empty}{what they will do}
  { \mom_add_action:nnnn {#1} {#2} {#3} {#4}
    \mom_item:nn { \momstr{task}~\int_use:N \g_mom_action_int }
      { #4 \bool_lazy_and:nnF { \tl_if_blank_p:n {#2} } { \tl_if_blank_p:n {#3} }
          { \newline {\color{mpslate}\small
            \tl_if_blank:nF {#2} { \momstr{owner}:~#2 \tl_if_blank:nF {#3} { \quad } }
            \tl_if_blank:nF {#3} { \momstr{deadline}:~#3 } } } } }
\cs_new_protected:Npn \mom_item:nn #1#2
  { \par\addvspace{3pt}\noindent
    \makebox[25mm][l]{\color{mpteal}\momlabel\small #1}%
    \parbox[t]{\dimexpr\linewidth-25mm\relax}{\RaggedRight #2 \strut}\par\addvspace{3pt} }
\NewDocumentCommand \needsconfirmation { m m } {}   % bodies written before 2026-09-27: unproven items are never printed
\NewDocumentCommand \nextmeeting { m }
  { \par\medskip{\color{mpteal}\momlabel\momstr{next}:}\enspace #1\par }
\ExplSyntaxOff

% ---------------------------------------------------------------- 6. page design
\newcommand\momlogo[1][30mm]{\includegraphics[width=#1]{\momtemplatedir logo.pdf}}  % vector; drawn from logo-colour.tex
\titleformat{\section}{\momsans\bfseries\large\color{mpteal}}{\thesection.}{0.5em}{}
\titlespacing*{\section}{0pt}{1.1em}{0.25em}
\setlist[itemize]{leftmargin=1.2em,itemsep=0.15em,topsep=0.2em,label={\color{mpteal}\textbullet}}
\setlist[enumerate]{leftmargin=1.6em,itemsep=0.15em,topsep=0.2em}

\fancypagestyle{mom}{%
  \fancyhf{}%
  \renewcommand\headrulewidth{0pt}%
  \fancyhead[L]{\momlogo[30mm]}%
  \fancyfoot[L]{\parbox[t]{0.78\textwidth}{\raggedright\momsans\scriptsize\color{mpslate}%
    \momstr{aifooter}}}%   AI Act Art. 50: the text is marked as drafted by AI
  \fancyfoot[R]{\momsans\scriptsize\color{mpslate}\momstr{page}\ \thepage\ \momstr{of}\ \pageref{LastPage}}%
  \renewcommand\footrule{\vspace*{-2pt}{\color{mpgold}\rule{\textwidth}{0.6pt}}\vspace{3pt}}}
\pagestyle{mom}

\newcommand\mom@meta[1]{\momhas{#1}{\par\noindent
  \parbox[t]{42mm}{\raggedright\textcolor{mpslate}{\momlabel\small\momstr{#1}}}\hspace{3mm}%
  \parbox[t]{\dimexpr\textwidth-45mm\relax}{\raggedright\momvalue{#1}}\par}{}}
\newcommand\mommaketitle{%
  {\momsans\fontsize{17}{22}\selectfont\color{mpteal}\raggedright
    {\bfseries\momstr{doc}\momhas{number}{\ \momstr{no}\,\momvalue{number}}{}}\ \momvalue{title}\par}
  \vspace{2pt}
  {\momsans\fontsize{12.5}{16}\selectfont\color{mpcharcoal}\momvalue{date}\momhas{time}{,\ \momvalue{time}}{}\par}
  \vspace{8pt}{\color{mpgold}\rule{\textwidth}{0.8pt}}\par\vspace{2pt}
  {\setlength\parskip{1pt}\mom@meta{place}\mom@meta{chair}\mom@meta{secretary}}\par}

% attendance: \begin{attendance}{present} \person{Name}{Role} ... \end{attendance}
\newenvironment{attendance}[1]
  {\par\vspace{4pt}{\momlabel\color{mpteal}\momstr{#1}}\momhas{quorum}{\enspace{\small\color{mpslate}(\momvalue{quorum})}}{}\par\vspace{-2pt}\begin{itemize}[label={},leftmargin=0pt,itemsep=0pt,parsep=0pt]}
  {\end{itemize}}
\newcommand\person[2]{\item #1\ifx\\#2\\\else{\color{mpslate}, #2}\fi}
\newenvironment{agenda}
  {\par\vspace{4pt}{\momlabel\color{mpteal}\momstr{agenda}}\par\vspace{-2pt}\begin{enumerate}}
  {\end{enumerate}}
\newcommand\agendaitem[2]{\item #2}
\newcommand\summary[2]{\par\vspace{4pt}{\momlabel\color{mpteal}\momstr{summary}}\par\vspace{2pt}#2\par}

\newcommand\mom@tablehead[1]{\rowcolor{mpteal}#1\\}
\newcommand\mom@h[1]{\leavevmode\textcolor{white}{\momsans\small\bfseries #1}}
\newcommand\momsummary{%
  \mom@ifdecisions{\begingroup
    \section*{\momstr{decisions}}
    \renewcommand\arraystretch{1.25}\rowcolors{2}{white}{mprow}
    \begin{xltabular}{\textwidth}{@{\hspace{4pt}}>{\raggedleft\arraybackslash}p{6mm}@{\hspace{8pt}}>{\raggedright\arraybackslash}X@{\hspace{4pt}}}
      \mom@tablehead{\mom@h{\#} & \mom@h{\momstr{decision}}}
      \endhead
      \mom@decisionrows
    \end{xltabular}\endgroup}%
  \mom@ifactions{\begingroup
    \section*{\momstr{actions}}
    \renewcommand\arraystretch{1.25}\rowcolors{2}{white}{mprow}\mom@actioncolumns
    \begin{xltabular}{\textwidth}{@{\hspace{4pt}}>{\raggedleft\arraybackslash}p{6mm}@{\hspace{8pt}}>{\raggedright\arraybackslash}XOW@{\hspace{4pt}}}
      \mom@tablehead{\mom@h{\#} & \mom@h{\momstr{task}}\mom@ifowners{ & \mom@h{\momstr{owner}}}\mom@ifdeadlines{ & \mom@h{\momstr{deadline}}}}
      \endhead
      \mom@actionrows
    \end{xltabular}\endgroup}}
\newcommand\mom@sign[1]{\momhas{#1}{\begin{minipage}[t]{0.47\textwidth}\raggedright
    \textcolor{mpslate}{\momlabel\small\momstr{#1}}\par\vspace{14pt}
    \rule{55mm}{0.4pt}\par\small\momvalue{#1}\end{minipage}\hfill}{}}
\newcommand\mom@signatures{%  % one line of two minipages, about 14 mm tall; it never splits
  \par\needspace{16mm}\vspace{4pt}\noindent\mom@sign{chair}\mom@sign{secretary}\par}
\newcommand\momsignatures{\momhas{chair}{\mom@signatures}{\momhas{secretary}{\mom@signatures}{}}}

% the document: \begin{minutes} (model-written body) \end{minutes}
\newenvironment{minutes}{\mommaketitle}{\momsummary\momsignatures}
\endinput
