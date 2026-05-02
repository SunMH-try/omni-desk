.PHONY: install seed-demo-data build-index serve test query meeting-context extract-actions weekly-window evaluate

install:
	pip install -r requirements.txt

seed-demo-data:
	python -m app seed-demo-data

build-index:
	python -m app build-index

serve:
	uvicorn app.main:app --reload --port 8000

test:
	pytest tests/ -v

query:
	python -m app query --q "Alpha 项目周会需要关注哪些延期风险？"

meeting-context:
	python -m app meeting-context --meeting-id meeting_alpha_weekly_next

extract-actions:
	python -m app extract-actions --minutes-id minutes_alpha_review

weekly-window:
	python -m app weekly-window --week 2026-W17

evaluate:
	python -m app evaluate
