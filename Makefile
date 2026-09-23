PROJECT_ROOT := $(CURDIR)
PRIVATE_CV_ROOT ?= $(PROJECT_ROOT)/private_data/cv
SOURCE_DIR ?= $(PRIVATE_CV_ROOT)/source
OUTDIR ?= $(PRIVATE_CV_ROOT)/build
LATEX_CLASS_DIR ?= $(PROJECT_ROOT)/cv/latex
TEXBIN ?= $(PROJECT_ROOT)/.TinyTeX/bin/x86_64-linux
export PATH := $(TEXBIN):$(PATH)
export TEXINPUTS := $(LATEX_CLASS_DIR):$(SOURCE_DIR):$(TEXINPUTS)

.PHONY: all bootstrap install-browser private-init private-check current visa clean check-tools daily weekly session-audit config-check workflow workflow-plan test public-audit history-audit release-check public-snapshot

CONFIG ?= job_bot/config.china_hk_ic_foreign.json

all: current visa

bootstrap:
	./scripts/bootstrap.sh

install-browser:
	./scripts/bootstrap.sh --with-browser

private-init:
	python3 -m job_bot.private_config init

private-check:
	python3 -m job_bot.private_config check

current:
	@mkdir -p $(OUTDIR)
	@command -v latexmk >/dev/null 2>&1 || { echo "latexmk not found. Install a TeX distribution or compile on Overleaf."; exit 127; }
	latexmk -cd -pdf -interaction=nonstopmode -halt-on-error -outdir=$(OUTDIR) $(SOURCE_DIR)/current.tex

visa:
	@mkdir -p $(OUTDIR)
	@command -v latexmk >/dev/null 2>&1 || { echo "latexmk not found. Install a TeX distribution or compile on Overleaf."; exit 127; }
	latexmk -cd -pdf -interaction=nonstopmode -halt-on-error -outdir=$(OUTDIR) $(SOURCE_DIR)/visa.tex

check-tools:
	@command -v latexmk >/dev/null 2>&1 && echo "latexmk: OK" || echo "latexmk: missing"
	@command -v biber >/dev/null 2>&1 && echo "biber: OK" || echo "biber: missing"
	@command -v pdflatex >/dev/null 2>&1 && echo "pdflatex: OK" || echo "pdflatex: missing"

clean:
	latexmk -C -cd -outdir=$(OUTDIR) $(SOURCE_DIR)/current.tex $(SOURCE_DIR)/visa.tex 2>/dev/null || true
	rm -f $(OUTDIR)/*.pdf

daily:
	python3 job_bot/daily_pipeline.py

weekly:
	python3 job_bot/weekly_report.py

session-audit:
	python3 application_bot/cli.py session-audit

config-check:
	python3 job_bot/config_inspect.py --config $(CONFIG)

workflow:
	@test -n "$(WORKFLOW)" || { echo "Set WORKFLOW, for example: make workflow WORKFLOW=http_refresh"; exit 2; }
	python3 job_bot/run_modules.py --config $(CONFIG) --workflow $(WORKFLOW)

workflow-plan:
	@test -n "$(WORKFLOW)" || { echo "Set WORKFLOW, for example: make workflow-plan WORKFLOW=http_refresh"; exit 2; }
	python3 job_bot/run_modules.py --config $(CONFIG) --workflow $(WORKFLOW) --dry-run

test:
	python3 -m unittest discover -s . -p 'test_*.py'

public-audit:
	python3 scripts/audit_public_repo.py

history-audit:
	python3 scripts/audit_public_repo.py --history

release-check: public-audit test config-check

public-snapshot: release-check
	@test -n "$(DEST)" || { echo "Set DEST, for example: make public-snapshot DEST=../26fall_intern_public"; exit 2; }
	python3 scripts/export_public_snapshot.py --init "$(DEST)"
