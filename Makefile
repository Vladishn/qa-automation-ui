# Unified Makefile for QA Automation backend + frontend + regression

# =====================
# Backend configuration
# =====================
BACKEND_DIR      := backend
BACKEND_VENV     := $(BACKEND_DIR)/.venv
BACKEND_APP      := app.main:app

# ======================
# Frontend configuration
# ======================
# frontend יכול להיות:
#  - תיקיית ./frontend בתוך TestProj
#  - או נתיב חיצוני שנשמר בקובץ .frontend_path (שורה אחת: pwd של ה-UI)
FRONTEND_NAME       := qa-automation-ui
FRONTEND_HINT_FILE  := .frontend_path

# ======================
# Regression artifacts
# ======================
REGRESSION_ARTIFACTS_DIR := backend/artifacts/regression
SESSION_ID ?= QS_TEST_001

# =====================
# Phony targets
# =====================
.PHONY: setup dev \
        backend-venv backend-install backend-run backend-stop backend-restart \
        frontend-install frontend-run frontend-stop \
        clean reset validate \
        session-json session-json-open

# =====================
# Backend targets
# =====================

backend-venv:
	@echo "[backend] creating virtualenv at $(BACKEND_VENV) (if missing)..."
	@if [ ! -d "$(BACKEND_VENV)" ]; then \
		cd $(BACKEND_DIR) && python3 -m venv .venv; \
	else \
		echo "[backend] virtualenv already exists."; \
	fi

backend-install: backend-venv
	@echo "[backend] installing requirements..."
	cd $(BACKEND_DIR) && .venv/bin/python -m pip install -U pip
	cd $(BACKEND_DIR) && .venv/bin/python -m pip install -r requirements.txt
	@echo "[backend] requirements installed."

backend-run: backend-venv
	@echo "[backend] starting uvicorn on http://127.0.0.1:8000 ..."
	cd $(BACKEND_DIR) && .venv/bin/python -m uvicorn $(BACKEND_APP) --reload --log-level debug

backend-stop:
	@echo "[backend] stopping any process on :8000..."
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || echo "[backend] nothing listening on :8000"

backend-restart: backend-stop
	@$(MAKE) backend-run

# ======================
# Frontend helper (resolve dir)
# ======================

define resolve_frontend_dir
if [ -d "frontend" ]; then \
	FRONTEND_DIR="./frontend"; \
elif [ -f "$(FRONTEND_HINT_FILE)" ]; then \
	echo "[frontend] reading path from $(FRONTEND_HINT_FILE)..."; \
	FRONTEND_DIR=$$(head -n 1 "$(FRONTEND_HINT_FILE)"); \
else \
	echo "[frontend] ERROR: no frontend path configured."; \
	echo "[frontend] Either create ./frontend or create $(FRONTEND_HINT_FILE) with absolute path to your UI project."; \
	exit 1; \
fi; \
echo "[frontend] using frontend dir: $$FRONTEND_DIR"; \
cd "$$FRONTEND_DIR"
endef

# ======================
# Frontend targets
# ======================

frontend-install:
	@echo "[frontend] npm install..."
	@$(resolve_frontend_dir) && npm install
	@echo "[frontend] npm install completed."

frontend-run:
	@echo "[frontend] npm run dev..."
	@$(resolve_frontend_dir) && npm run dev

frontend-stop:
	@echo "[frontend] stopping any process on :5173..."
	@lsof -ti:5173 | xargs kill -9 2>/dev/null || echo "[frontend] nothing listening on :5173"

# ======================
# High-level workflow targets
# ======================

# פעם ראשונה / בודק חדש / מכונה חדשה
setup: backend-install frontend-install

# dev מלא – מריץ backend + frontend ביחד
dev:
	@echo "[dev] starting backend + frontend (Ctrl+C to stop)..."
	@$(MAKE) -j2 backend-run frontend-run

# ======================
# Housekeeping
# ======================

clean:
	@echo "[clean] removing Python __pycache__ under $(BACKEND_DIR)..."
	find $(BACKEND_DIR) -name "__pycache__" -type d -exec rm -rf {} +
	@echo "[clean] done."

reset: backend-stop frontend-stop
	@echo "[reset] clearing backend venv and frontend node_modules..."
	rm -rf $(BACKEND_VENV)
	@$(resolve_frontend_dir) && rm -rf node_modules || echo "[reset] skipping frontend cleanup (not configured)"
	@echo "[reset] done. Run 'make setup' again."

# ======================
# Quick validation
# ======================

validate:
	@echo "[validate] compiling backend..."
	cd $(BACKEND_DIR) && .venv/bin/python -m compileall app || { echo "[validate] backend compile failed"; exit 1; }
	@echo "[validate] checking backend /health (make sure backend is running)..."
	@curl -sf http://127.0.0.1:8000/health >/dev/null \
		&& echo "[validate] backend health OK" \
		|| echo "[validate] backend health FAILED (is backend up?)"

# ======================
# Regression: export session JSON
# ======================

session-json:
	@mkdir -p $(REGRESSION_ARTIFACTS_DIR)
	@echo "[regression] exporting session $(SESSION_ID) to JSON..."
	@curl -s "http://127.0.0.1:8000/sessions/$(SESSION_ID)/snapshot" \
		-o "$(REGRESSION_ARTIFACTS_DIR)/session_$(SESSION_ID).json" \
		&& echo "[regression] snapshot saved to $(REGRESSION_ARTIFACTS_DIR)/session_$(SESSION_ID).json" \
		|| echo "[regression] ERROR: failed to fetch snapshot (is backend running? correct SESSION_ID?)"

session-json-open:
	@echo "[regression] showing snapshot for $(SESSION_ID):"
	@cat "$(REGRESSION_ARTIFACTS_DIR)/session_$(SESSION_ID).json" || echo "[regression] file not found. Run 'make session-json SESSION_ID=...' first."

##############################################################
# Regression – Session Snapshot Collection + Inspect + Diff
##############################################################

REGRESSION_DIR := backend/artifacts/regression
SESSION_ID ?=
BASE ?=
HEAD ?=

collect:
	@if [ -z "$(SESSION_ID)" ]; then echo "Usage: make collect SESSION_ID=QS_xxx"; exit 1; fi
	@mkdir -p $(REGRESSION_DIR)
	@echo "[regression] collecting snapshot for $(SESSION_ID)..."
	# שים לב: ה-router של sessions משתמש ב-prefix '/sessions'
	# וה-נתיב שהקונקטור הוסיף הוא '/sessions/{session_id}/snapshot'
	# לכן הנתיב המלא הוא:
	#   /sessions/sessions/{session_id}/snapshot
	@curl -s "http://127.0.0.1:8000/sessions/sessions/$(SESSION_ID)/snapshot" \
		-o "$(REGRESSION_DIR)/session_$(SESSION_ID).json" \
		&& echo "[regression] saved → $(REGRESSION_DIR)/session_$(SESSION_ID).json" \
		|| echo "[regression] ERROR: session not found or backend down."

inspect:
	@if [ -z "$(SESSION_ID)" ]; then echo "Usage: make inspect SESSION_ID=QS_xxx"; exit 1; fi
	@echo "[regression] opening session JSON for $(SESSION_ID):"
	@cat "$(REGRESSION_DIR)/session_$(SESSION_ID).json" || echo "File not found."

compare:
	@if [ -z "$(BASE)" ] || [ -z "$(HEAD)" ]; then \
		echo "Usage: make compare BASE=QS_xxx HEAD=QS_yyy"; exit 1; \
	fi
	@echo "[regression] comparing BASE=$(BASE) <-> HEAD=$(HEAD)"
	@diff -u \
		"$(REGRESSION_DIR)/session_$(BASE).json" \
		"$(REGRESSION_DIR)/session_$(HEAD).json" \
		|| true
