### ============================
###  GLOBAL SETTINGS
### ============================

SHELL := /bin/bash


### ============================
###  BACKEND TASKS (FastAPI)
### ============================

# הפעלה מקומית של ה-backend עם uvicorn + venv
backend-dev:
	@echo "Starting backend..."
	@cd backend && \
		source ../.venv/bin/activate && \
		uvicorn app.main:app --reload --log-level debug

# הפעלת בדיקות backend (pytest)
backend-test:
	@echo "Running backend tests..."
	@cd backend && \
		source ../.venv/bin/activate && \
		pytest -s


### ============================
### FRONTEND TASKS (React + Vite)
### ============================

# הרצת ממשק הבדיקות (UI)
frontend-dev:
	@echo "Starting frontend (Vite dev server)..."
	@cd src && npm run dev

# בניית פרודקשן
frontend-build:
	@echo "Building frontend..."
	@cd src && npm install && npm run build

# בדיקות frontend (אם יהיה vitest / jest בעתיד)
frontend-test:
	@echo "Running frontend tests..."
	@cd src && npm test


### ============================
### INSTALLATION TASKS
### ============================

# התקנת backend requirements
install-backend:
	@echo "Installing backend dependencies..."
	@python3 -m venv .venv
	@source .venv/bin/activate && pip install --upgrade pip && pip install -r backend/requirements.txt

# התקנת frontend deps
install-frontend:
	@echo "Installing frontend npm packages..."
	@cd src && npm install

# התקנת הכל
install:
	@$(MAKE) install-backend
	@$(MAKE) install-frontend


### ============================
### CLEANUP TASKS
### ============================

clean-pycache:
	find . -type d -name "__pycache__" -exec rm -rf {} +

clean-build:
	rm -rf src/dist

clean: clean-pycache clean-build


### ============================
### COMBINED SHORTCUTS
### ============================

# הרצה משולבת – backend + frontend
dev:
	@echo "Starting full stack (backend + frontend)..."
	@echo "Backend on: http://127.0.0.1:8000"
	@echo "Frontend on: http://127.0.0.1:5173"
	@$(MAKE) -j2 backend-dev frontend-dev

