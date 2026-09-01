# Pin the engine to pdfTeX. The system-wide /etc/LatexMk sets $pdf_mode = 4
# (lualatex), which disagreed with the editor's own pdflatex build: the two
# alternated on the same aux files, and the NFSS weight names this preamble
# uses (medium, regular) exist only under pdfTeX's T1 encoding, silently
# falling back to Light under LuaTeX's fontspec/TU.
$pdf_mode = 1;

# The deliverable belongs at the project root, the auxiliaries do not. latexmk
# compiles here and moves the finished PDF up one level, so `latexmk -c` still
# clears this folder and leaves ../main.pdf standing.
$out_dir = "..";
$aux_dir = ".";
