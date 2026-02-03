![CI](https://github.com/dhcsousa/hospitopt/actions/workflows/ci.yaml/badge.svg)
[![codecov](https://codecov.io/github/dhcsousa/hospitopt/graph/badge.svg?token=24SLLFHARQ)](https://codecov.io/github/dhcsousa/hospitopt)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

# HospitOPT

A Python-based optimization system that uses constraint programming to maximize the number of lives saved in emergency medical scenarios. The system models hospitals, available beds, ambulance positions, and patient needs, then computes optimized resource allocations to improve medical response and outcomes during mass casualty events.

![HospitOPT Demo](https://github.com/user-attachments/assets/11f9cd9f-84df-4abf-8f27-bc27bd5eda91)

## Overview

HospitOPT is built as a microservices architecture with three main components:

- **REST API** (`hospitopt-api`): FastAPI-based service providing access to resources (hospitals, patients, ambulances) and optimization results
- **Optimization Worker** (`hospitopt-worker`): Background service that continuously monitors for changes and runs constraint programming optimization using Pyomo and Google Maps routing data
- **Web Dashboard** (`frontend`): Interactive Reflex-based dashboard for visualizing assignments and system metrics

The system automatically re-optimizes ambulance-to-hospital assignments whenever inputs change, ensuring timely medical response for all patients while respecting capacity constraints and urgency deadlines.

## Architecture

### REST API (`hospitopt-api`)

FastAPI-based REST service that provides access to:

- **Resources**: GET endpoints for hospitals, patients, and ambulances (paginated)
- **Assignments**: GET endpoint for patient-to-hospital-ambulance assignments with optimization metadata
- **Health**: Health check endpoint for monitoring

The API uses API key authentication and CORS middleware for secure cross-origin access. It connects to PostgreSQL to serve the current state of the system.

**Key Features:**
- Async SQLAlchemy for database operations
- Paginated responses (configurable limits)
- YAML-based configuration
- CORS support for frontend integration

### Optimization Worker (`hospitopt-worker`)

Background polling service that monitors the database for changes and triggers optimization when needed.

**Workflow:**
1. Polls database for hospitals, patients, and ambulances
2. Computes hash of inputs to detect changes
3. When changes detected:
   - Fetches travel time matrices from Google Maps Routes API
   - Builds constraint programming model using Pyomo
   - Solves MILP to maximize lives saved while respecting:
     - Hospital bed capacity constraints
     - Ambulance availability
     - Patient urgency deadlines (time to hospital)
   - Writes optimized assignments to database

**Optimization Objective:**
Maximizes the number of patients who receive timely care by assigning each patient to an ambulance and hospital such that the total travel time (ambulance→patient→hospital) is within the patient's urgency deadline. Uses urgency-weighted objective to prioritize critical cases.

**Features:**
- Real-time travel time calculations using Google Maps
- Speed factor adjustment for priority ambulance transport (default 30% faster)
- Flags cases requiring aerial evacuation when ground transport is insufficient
- Capacity and resource shortfall detection

### Web Dashboard (`frontend`)

Interactive Reflex-based dashboard providing real-time visualization of the optimization system.

**Features:**
- **Map View**: Displays hospitals, patients, and ambulances with color-coded assignments
- **Assignments Table**: Detailed view of patient allocations with travel times and deadlines
- **Metrics Panel**:
  - Assigned ambulance percentage
  - Patients requiring urgent aerial extraction
  - Hospital bed occupancy
- **Auto-refresh**: Polls API every 5 seconds for updates
- **Health monitoring**: Displays API connection status

## Prerequisites

- **Python 3.14+**
- **PostgreSQL** (for data storage)
- **Google Maps API Key** (for route calculations)
- **MILP Solver** - GLPK (open-source) or another Pyomo-compatible solver

Install GLPK on macOS:
```bash
brew install glpk
```

On Linux:
```bash
sudo apt-get install glpk-utils
```

## Getting Started

### 1. Environment Setup

This project uses `uv` to manage Python dependencies and workspaces.

```bash
uv sync --all-groups --all-packages
```

This creates a virtual environment and installs all dependencies from the workspace packages (api, worker, core) and development tools.

### 2. Configuration

Copy the example environment file and configure your secrets:

```bash
cp .env.example .env
```

Edit `.env` and set:
- `HOSPITOPT_DB_PASSWORD`: PostgreSQL password
- `HOSPITOPT_API_KEY`: API key for authentication
- `GOOGLE_MAPS_API_KEY`: Your Google Maps API key

### 3. Database Setup

Start PostgreSQL using Docker Compose:

```bash
docker compose up -d db
```

Wait for the database to be ready, then run migrations:

```bash
alembic upgrade head
```

(Optional) Seed the database with sample data:

```bash
uv run scripts/seed_db.py
```

### 4. Running the Services

#### Option A: Kubernetes (Comming Soon)

#### Option B: Using Docker Compose (Recommended)

To use the published images from GHCR without building, run:

```bash
docker compose up -d
```

To build the images locally:

```bash
docker compose up -d --build
```

This starts:
- PostgreSQL database (port 5432)
- REST API (port 8000)
- Optimization worker (background)
- Reflex frontend (port 3000)

#### Option C: Running Services Individually

The `.vscode/launch.json` file includes configurations to run each service in debug mode.

**API Server:**
```bash
export API_CONFIG_FILE_PATH=configs/api.yaml
uv run uvicorn hospitopt_api.main:app --reload
```

**Optimization Worker:**
```bash
export WORKER_CONFIG_FILE_PATH=configs/worker.yaml
uv run python packages/worker/src/hospitopt_worker/main.py
```

**Frontend Dashboard:**
```bash
cd frontend
reflex run
```

The frontend will be available at `http://localhost:3000` and the API at `http://localhost:8000` by default.

### 5. Using the System

1. **Add Resources**: Use the API or seed script to add hospitals, patients, and ambulances
2. **Monitor Optimization**: The worker will automatically detect changes and optimize assignments
3. **View Dashboard**: Open the frontend to see real-time assignments and metrics
4. **Query Results**: Use the `/assignments` endpoint to retrieve optimized allocations

## API Endpoints

- `GET /health` - Health check
- `GET /hospitals` - List hospitals (paginated)
- `GET /patients` - List patients (paginated)
- `GET /ambulances` - List ambulances (paginated)
- `GET /assignments` - List patient assignments (paginated, sorted by optimization time)

All resource endpoints except `/health` require API key authentication via `Authorization: Bearer <API_KEY>` header.

## Development

### Running Tests

```bash
uv run pytest
```

This runs the full test suite with coverage reporting (minimum 90% required).

### Pre-commit Hooks

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Hooks include: ruff (linting/formatting), mypy (type checking), and bandit (security scanning).

## Project Structure

```
hospitopt/
├── packages/
│   ├── api/          # FastAPI REST service
│   ├── worker/       # Background optimization engine
│   └── core/         # Shared domain models and database logic
├── frontend/         # Reflex web dashboard
├── configs/          # YAML configuration files
├── alembic/          # Database migrations
├── tests/            # Test suite (unit + integration)
├── scripts/          # Utility scripts (e.g., database seeding)
└── docker-compose.yaml
```
