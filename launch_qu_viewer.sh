#!/usr/bin/env bash
# QU Viewer launcher — activates the narnia conda environment then opens the app.
# Double-click this in a file manager, or run from terminal.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_BASE="${HOME}/anaconda3"
ENV_PYTHON="${CONDA_BASE}/envs/narnia/bin/python3"

source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate narnia

exec "${ENV_PYTHON}" "${SCRIPT_DIR}/qu_viewer.py" "$@"
