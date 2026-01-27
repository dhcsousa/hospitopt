![CI: Pre-commit & Tests](https://github.com/dhcsousa/hospitopt/actions/workflows/checks.yaml/badge.svg)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

# hospitopt

Python-based optimization project that uses constraint programming to maximize the number of lives saved in emergency and healthcare scenarios. It models hospitals, diseases, available beds, ambulance positions and capacities, and patient needs, then computes optimized resource allocations to improve medical response and outcomes.

## Environment Setup

The current project useses `uv` to manage the Python environment. To set up the environment, run:

```bash
uv sync --all-groups
```

This command will create a virtual environment and install all the required dependencies specified in the `pyproject.toml` file.

## Optimization Idea

The core idea behind the optimization in this project is to use constraint programming to allocate medical resources efficiently. By modeling the various constraints and requirements of hospitals, patients, and ambulances, the system can determine the best way to distribute resources to maximize the number of lives saved. This involves considering factors such as hospital capacities, patient needs, ambulance locations, and disease characteristics (which map to maximum time to be in hospital) to make informed decisions about resource allocation. If a mass casualty event occurs, the system can quickly adapt and re-optimize the allocation of resources to respond effectively to the new situation, it will always ensure that the maximum number of patients receive the care they need in a timely manner. It will also flag if there is the need to launch an aerial evacuation to save more lives.

To sucessfully use Pyomo first install GLPK or set up another MILP solver.


## Database (Postgres)

For local development, start Postgres with Docker Compose.

1) Copy `.env.example` to `.env` and set `HOSPITOPT_DB_PASSWORD` to match the database password.
2) Start the database:

```bash
docker compose up -d db
```

To stop it:

```bash
docker compose down
```

The default connection values in [configs/app.yaml](configs/app.yaml) are already aligned with the compose setup.

To run the database migrations, use:

```bash
alembic upgrade head
```

## Running the Worker

To run the worker, use the following command:

```bash
uv run src/core/worker/main.py
```

You might also use the run/debug configurations, `.vscode/launch.json` is already set up for that.
