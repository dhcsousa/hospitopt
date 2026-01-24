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
