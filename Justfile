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
