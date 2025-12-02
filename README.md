# QuickSet QA Automation CLI

## Initial setup (run only once)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running a scenario
```bash
source .venv/bin/activate
python -m src.cli run --session-id VS_TEST_001 --stb-ip 192.168.1.125 --scenario TV_AUTO_SYNC
```

## Summarizing an existing session
```bash
source .venv/bin/activate
python -m src.cli summarize --session-id VS_TEST_001 --scenario TV_AUTO_SYNC
```
## Git Workflow
לזרימת עבודה מומלצת עם Git עבור הפרויקט:
[GIT_WORKFLOW.md](./GIT_WORKFLOW.md)
