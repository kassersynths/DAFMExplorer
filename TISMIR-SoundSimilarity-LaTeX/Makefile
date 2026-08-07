# Build the TISMIR manuscript with pdflatex + bibtex.
# Usage: make        (full cycle)
#        make clean  (remove auxiliaries)
#        make view   (open PDF if a viewer is available)

MAIN = main
LATEX = pdflatex
BIBTEX = bibtex
LATEXFLAGS = -interaction=nonstopmode -halt-on-error

.PHONY: all pdf clean view

all: pdf

pdf: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex references.bib tismir.sty
	$(LATEX) $(LATEXFLAGS) $(MAIN)
	$(BIBTEX) $(MAIN)
	$(LATEX) $(LATEXFLAGS) $(MAIN)
	$(LATEX) $(LATEXFLAGS) $(MAIN)

clean:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).blg $(MAIN).log \
	      $(MAIN).out $(MAIN).toc $(MAIN).lof $(MAIN).lot \
	      $(MAIN).synctex.gz $(MAIN).fls $(MAIN).fdb_latexmk \
	      $(MAIN).pdf

view: $(MAIN).pdf
	@command -v open >/dev/null && open $(MAIN).pdf || \
	 command -v xdg-open >/dev/null && xdg-open $(MAIN).pdf || \
	 command -v start >/dev/null && start $(MAIN).pdf || \
	 echo "PDF built: $(MAIN).pdf"
