# Template assets

| File | What it is | Source | Licence |
|---|---|---|---|
| `logo-colour.tex`, `logo-white.tex`, `logo.png` | The Medpark logo, redrawn as TikZ paths from the SVG on medpark.md | `https://www.medpark.md/wp-content/themes/newmedpark/images/logo.svg` | Medpark's trademark, used for Medpark's own challenge prototype; confirm with Medpark before any other use |
| `fonts/Montserrat-*.ttf` | Headings; Medpark's website font | github.com/JulietaUla/Montserrat | SIL Open Font License 1.1 (`fonts/OFL-Montserrat.txt`) |
| `fonts/PT_Serif-Web-*.ttf` | Body text; designed for Latin and Cyrillic, covers Romanian ș ț ă â î | github.com/google/fonts (ofl/ptserif) | SIL Open Font License 1.1 (`fonts/OFL-PTSerif.txt`) |

Brand colours, read from medpark.md's own pages: teal `#008286`, gold `#DAB027`,
light yellow `#F5EA61`, slate `#515963`, charcoal `#403E3D`.

`logo.png` is rendered from `logo-standalone.tex`:
`xelatex logo-standalone.tex && pdftoppm -r 300 -png -singlefile logo-standalone.pdf logo`.

The DOCX names the same two fonts. Install them from `fonts/` on the computers
that open the DOCX; the PDF embeds them and needs nothing.
