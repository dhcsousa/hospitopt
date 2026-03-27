bump step:
    uv version --bump {{ step }}
    uv version --package hospitopt-core --bump {{ step }}
    uv version --package hospitopt-worker --bump {{ step }}
    uv version --package hospitopt-api --bump {{ step }}
    yq -i '.appVersion = "'$(uv version --short)'"' charts/hospitopt/Chart.yaml

sync:
    uv sync --all-groups --all-packages
    if [[ ! -x .git/hooks/pre-commit ]]; then uv run pre-commit install; fi

test:
    uv run pytest

migrate:
    alembic upgrade head

api:
    uv run uvicorn hospitopt_api.main:app --reload

worker:
    uv run python packages/worker/src/hospitopt_worker/main.py

frontend:
    cd frontend && reflex run

schemas:
    uv run python scripts/export_schemas.py

fake-api api_key tick="0.2" speed="1" ambulances="30" incident_tick="10" incident_patients="24":
    uv run python scripts/fake_api.py --api-url http://localhost:8000 --api-key {{ api_key }} --tick {{ tick }} --speed {{ speed }} --ambulances {{ ambulances }} --incident-tick {{ incident_tick }} --incident-patients {{ incident_patients }}
