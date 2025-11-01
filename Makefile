

SHELL := /bin/bash

# .env varsa içeri aktar (export)
-include .env
export $(shell sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' .env 2>/dev/null)

.PHONY: help install dev test demo obs-up obs-down fmt lint

help:
	@echo "Targets:"
	@echo "  make install     - pip ile bağımlılıkları kur"
	@echo "  make dev         - uvicorn (reload) ile API'yi çalıştır"
	@echo "  make test        - pytest"
	@echo "  make demo        - sentetik trafik + metrik/alert gösterimi"
	@echo "  make obs-up      - Prometheus + Grafana yığını"
	@echo "  make obs-down    - Observability yığınını kapat"

install:
	python -m pip install -U pip
	pip install -r requirements.txt || true

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	ENV=test PYTHONPATH=$$(pwd) pytest -q

demo:
	BASE_URL=$${BASE_URL:-http://127.0.0.1:8000} \
	IP=$${IP:-198.51.100.23} \
	bash app/scripts/demo.sh

obs-up:
	docker compose -f ops/compose.observability.yml up -d

obs-down:
	docker compose -f ops/compose.observability.yml down