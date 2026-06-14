.PHONY: db docs news register api ui eval install down scheduler

install:        ## install backend deps
	pip install -r requirements.txt

db:             ## start Postgres + pgvector
	docker compose up -d

down:           ## stop the database
	docker compose down

docs:           ## build the document corpus (regulation + RTS/ITS + ESMA/EBA → reg_chunks + register)
	python -m app.rag.docs_ingest

news:           ## poll RSS feeds → full-text news corpus
	python -m app.news.poll

register:       ## sync the real ESMA registers + read white papers for token names
	python -m app.register.sync --refresh && python -m app.register.whitepapers

scheduler:      ## run continuous news polling
	python -m app.news.scheduler

api:            ## run the FastAPI backend (Swagger at :8000/docs)
	uvicorn app.main:app --reload --port 8000

ui:             ## run the Next.js UI (:3000)
	cd frontend && npm install && npm run dev

eval:           ## run the evaluation harness end-to-end
	python -m eval.run --e2e --judge
