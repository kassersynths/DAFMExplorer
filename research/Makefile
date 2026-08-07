# Research pipeline DAG. Run from research/.
# Select machine profile with:  set DAFM_MACHINE=a|b

PY ?= python
DAFM ?= $(PY) -m dafm_audio.cli
export PYTHONPATH := $(CURDIR)$(if $(PYTHONPATH),$(PATHSEP)$(PYTHONPATH),)

.PHONY: help doctor status install install-node \
	corpus check-corpus render-manifest render-gain render encode-flac check-render \
	features check-features spaces check-spaces evaluate check-eval \
	morph hf-export figures hw-vgm hw-emu-reference hw-compare \
	test smoke lint inertness-audit

help:
	@echo "DAFM research pipeline"
	@echo "  make doctor          environment check"
	@echo "  make status          where am I / what next"
	@echo "  make corpus          Phase 0A/0B"
	@echo "  make check-corpus    gate after corpus"
	@echo "  make render-manifest build render queue"
	@echo "  make render-gain     probe peaks, set global gain"
	@echo "  make render          render one/all shards (see machines.yaml)"
	@echo "  make encode-flac     WAV -> 24-bit FLAC"
	@echo "  make check-render    gate after render"
	@echo "  make features        Family A (+ B if torch present)"
	@echo "  make spaces evaluate morph hf-export figures"
	@echo "  make test / smoke"

install:
	$(PY) -m pip install -e ".[dev]"

install-node:
	cd render && npm install

doctor:
	$(DAFM) doctor

status:
	$(DAFM) status

corpus:
	$(DAFM) corpus

check-corpus:
	$(DAFM) check-corpus

render-manifest: corpus
	$(DAFM) render-manifest

render-gain: render-manifest install-node
	$(DAFM) render-gain --shard 0/1

# Override SHARD=i/N to render a specific shard. Default uses profile range tip.
SHARD ?= 0/1
LIMIT ?=

render: render-manifest install-node
	$(DAFM) render --shard $(SHARD) $(if $(LIMIT),--limit $(LIMIT),)

encode-flac:
	$(DAFM) encode-flac --shard $(SHARD) $(if $(LIMIT),--limit $(LIMIT),)

check-render:
	$(DAFM) check-render

features:
	$(DAFM) features $(if $(LIMIT),--limit $(LIMIT),)

check-features:
	$(DAFM) check-features

spaces:
	$(DAFM) spaces $(if $(LIMIT),--limit $(LIMIT),)

check-spaces:
	$(DAFM) check-spaces

evaluate:
	$(DAFM) evaluate $(if $(LIMIT),--limit $(LIMIT),)

check-eval:
	$(DAFM) check-eval

morph:
	$(DAFM) morph

hf-export:
	$(DAFM) hf-export

figures:
	$(DAFM) figures

hw-vgm:
	$(DAFM) hw-vgm

hw-emu-reference: install-node
	cd hardware && node --import tsx vgm_player.ts

hw-compare:
	$(PY) hardware/compare_hw_emu.py

inertness-audit: install-node
	$(DAFM) inertness-audit

test:
	$(PY) -m pytest -q

smoke: install-node
	$(DAFM) corpus
	$(DAFM) check-corpus
	$(DAFM) render-manifest
	$(DAFM) render-gain --shard 0/1 --limit 10
	$(DAFM) render --shard 0/1 --limit 10
	$(DAFM) features --limit 10 --family a
	$(DAFM) spaces --limit 10
	$(DAFM) evaluate --limit 10 --experiment E1
	$(DAFM) morph

lint:
	$(PY) -m ruff check dafm_audio tests
