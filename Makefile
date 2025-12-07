##############################################################
# QA AUTOMATION MASTER MAKEFILE
# Backend + Frontend + Regression Snapshots
##############################################################

BACKEND_DIR      := backend
BACKEND_VENV     := $(BACKEND_DIR)/.venv
BACKEND_APP      := app.main:app

FRONTEND_PATH_FILE := .frontend_path

REGRESSION_DIR   := backend/artifacts/regression
SESSION_ID ?=
BASE ?=
HEAD ?=

.PHONY: \
	setup dev \
	backend-venv backend-install backend-run backend-stop backend-restart \
	frontend-install frontend-run frontend-stop \
	clean reset validate \
	collect inspect compare regression-report last diff-latest

##############################################################
# Backend
##############################################################

backend-venv:
	@echo "[backend] creating virtualenv (if missing)..."
	@if [ ! -d "$(BACKEND_VENV)" ]; then \
		cd $(BACKEND_DIR) && python3 -m venv .venv; \
	else \
		echo "[backend] virtualenv already exists."; \
	fi

backend-install: backend-venv
	@echo "[backend] installing requirements..."
	cd $(BACKEND_DIR) && .venv/bin/python -m pip install -U pip
	cd $(BACKEND_DIR) && .venv/bin/python -m pip install -r requirements.txt

backend-run:
	@echo "[backend] starting API server on :8000..."
	cd $(BACKEND_DIR) && .venv/bin/python -m uvicorn $(BACKEND_APP) --reload --log-level debug

backend-stop:
	@echo "[backend] stopping any process on :8000..."
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || echo "[backend] already stopped."

backend-restart: backend-stop backend-run

##############################################################
# Frontend
##############################################################

# helper פנימי למציאת נתיב פרונט
detect-frontend:
	@front=""; \
	if [ -f "$(FRONTEND_PATH_FILE)" ]; then \
		path_file=$$(cat "$(FRONTEND_PATH_FILE)"); \
		if [ -d "$$path_file" ]; then front="$$path_file"; fi; \
	fi; \
	if [ -z "$$front" ] && [ -d "frontend" ]; then front="./frontend"; fi; \
	if [ -z "$$front" ]; then \
		echo "[frontend] ERROR: frontend directory not found."; \
		echo "  - create 'frontend' under TestProj,"; \
		echo "    or put absolute path in .frontend_path"; \
		exit 1; \
	fi; \
	echo "$$front"

frontend-install:
	@front=$$(make -s detect-frontend); \
	echo "[frontend] npm install in $$front"; \
	cd "$$front" && npm install

frontend-run:
	@front=$$(make -s detect-frontend); \
	echo "[frontend] running dev server in $$front"; \
	cd "$$front" && npm run dev

frontend-stop:
	@echo "[frontend] stopping any process on :5173..."
	@lsof -ti:5173 | xargs kill -9 2>/dev/null || echo "[frontend] already stopped."

##############################################################
# High-level workflow
##############################################################

setup: backend-install frontend-install

dev:
	@echo "[dev] starting backend + frontend..."
	@$(MAKE) -j2 backend-run frontend-run

##############################################################
# Cleanup & validation
##############################################################

clean:
	@echo "[clean] removing __pycache__..."
	find $(BACKEND_DIR) -name "__pycache__" -type d -exec rm -rf {} +

reset: backend-stop frontend-stop
	@echo "[reset] removing backend venv..."
	rm -rf $(BACKEND_VENV)

validate:
	@echo "[validate] compiling backend..."
	cd $(BACKEND_DIR) && .venv/bin/python -m compileall app
	@echo "[validate] checking /health..."
	@curl -sf http://127.0.0.1:8000/health >/dev/null \
		&& echo "[validate] backend OK" \
		|| echo "[validate] backend FAIL"

##############################################################
# Regression – collect, inspect, compare
##############################################################

collect:
	@if [ -z "$(SESSION_ID)" ]; then echo "Usage: make collect SESSION_ID=QS_xxx"; exit 1; fi
	@mkdir -p "$(REGRESSION_DIR)"
	@echo "[regression] collecting snapshot for $(SESSION_ID) from /api/sessions/$(SESSION_ID)..."
	@curl -fsS "http://127.0.0.1:8000/api/sessions/$(SESSION_ID)" \
		-o "$(REGRESSION_DIR)/session_$(SESSION_ID).json" \
		&& echo "[regression] saved → $(REGRESSION_DIR)/session_$(SESSION_ID).json" \
		|| (echo "[regression] ERROR: collect failed (backend down? session missing?)"; rm -f "$(REGRESSION_DIR)/session_$(SESSION_ID).json"; exit 1)

inspect:
	@if [ -z "$(SESSION_ID)" ]; then echo "Usage: make inspect SESSION_ID=QS_xxx"; exit 1; fi
	@file="$(REGRESSION_DIR)/session_$(SESSION_ID).json"; \
	if [ ! -f "$$file" ]; then \
		echo "[inspect] file not found: $$file"; exit 1; \
	fi; \
	echo "[inspect] printing $$file"; \
	cat "$$file"

compare:
	@if [ -z "$(BASE)" ] || [ -z "$(HEAD)" ]; then \
		echo "Usage: make compare BASE=QS_xxx HEAD=QS_yyy"; exit 1; \
	fi
	@f1="$(REGRESSION_DIR)/session_$(BASE).json"; \
	f2="$(REGRESSION_DIR)/session_$(HEAD).json"; \
	if [ ! -f "$$f1" ] || [ ! -f "$$f2" ]; then \
		echo "[compare] both files must exist:"; \
		echo "  $$f1"; echo "  $$f2"; exit 1; \
	fi; \
	echo "[compare] BASE=$(BASE)  HEAD=$(HEAD)"; \
	diff -u "$$f1" "$$f2" || true

regression-report:
	@if [ -z "$(SESSION_ID)" ]; then echo "Usage: make regression-report SESSION_ID=QS_xxx"; exit 1; fi
	@echo "[regression] report for $(SESSION_ID)..."
	@cd $(BACKEND_DIR) && .venv/bin/python tools/regression_report.py "$(SESSION_ID)"

last:
	@if [ ! -d "$(REGRESSION_DIR)" ]; then echo "[last] no regression dir: $(REGRESSION_DIR)"; exit 1; fi
	@latest=$$(ls -t $(REGRESSION_DIR)/session_*.json 2>/dev/null | head -n 1); \
	if [ -z "$$latest" ]; then echo "[last] no snapshots found"; exit 1; fi; \
	echo "[last] latest file: $$latest"; \
	sid=$$(basename "$$latest" .json | sed 's/^session_//'); \
	echo "[last] SESSION_ID=$$sid"

diff-latest:
	@if [ ! -d "$(REGRESSION_DIR)" ]; then echo "[diff-latest] no regression dir: $(REGRESSION_DIR)"; exit 1; fi
	@files=$$(ls -t $(REGRESSION_DIR)/session_*.json 2>/dev/null | head -n 2); \
	count=$$(echo "$$files" | wc -l | tr -d ' '); \
	if [ "$$count" -lt 2 ]; then echo "[diff-latest] need at least 2 snapshots"; exit 1; fi; \
	f1=$$(echo "$$files" | sed -n '1p'); \
	f2=$$(echo "$$files" | sed -n '2p'); \
	echo "[diff-latest] comparing (older) $$f2  ->  (newer) $$f1"; \
	diff -u "$$f2" "$$f1" || true
