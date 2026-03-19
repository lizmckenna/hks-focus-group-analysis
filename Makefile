VENV = .venv
PYTHON = $(VENV)/bin/python
SCRIPTS = scripts

.PHONY: all parse themes curate keywords sentiment visualizations report clean

all: parse themes curate keywords sentiment visualizations report
	@echo "Pipeline complete. Open site/index.html to preview."

parse:
	cd $(SCRIPTS) && ../$(PYTHON) 01_parse_transcripts.py

themes: parse
	cd $(SCRIPTS) && ../$(PYTHON) 02_thematic_analysis.py

curate: themes
	cd $(SCRIPTS) && ../$(PYTHON) 07_apply_theme_config.py

keywords: curate
	cd $(SCRIPTS) && ../$(PYTHON) 03_keywords_cooccurrence.py

sentiment: curate
	cd $(SCRIPTS) && ../$(PYTHON) 04_sentiment.py

visualizations: sentiment keywords
	cd $(SCRIPTS) && ../$(PYTHON) 05_visualizations.py

report: visualizations curate
	cd $(SCRIPTS) && ../$(PYTHON) 06_build_report.py

clean:
	rm -rf data/*.csv data/*.json data/*.npy data/charts site/

encrypt:
	npx staticrypt site/**/*.html -p "$(PASSWORD)" -o site-encrypted/
	@echo "Encrypted site at site-encrypted/"
