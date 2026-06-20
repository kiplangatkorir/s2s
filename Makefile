install:
	pip install -e .

run-gateway:
	uvicorn gateway.ws_server:app --reload --host 0.0.0.0 --port 8000

run-frontend:
	cd frontend && npm run dev

deploy-gateway:
	python -m modal deploy gateway/modal_app.py

check-deepseek:
	python -m modal run gateway/modal_app.py::main --check-deepseek
