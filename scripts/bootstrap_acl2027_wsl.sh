#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv="$repo/.venv-acl2027-wsl"
data_root="${ALFWORLD_DATA:-$HOME/ALFWORLD_DATA}"

echo "Repository: $repo"
echo "Python: $(python3 --version)"

if [[ ! -d "$venv" ]]; then
  python3 -m venv "$venv"
fi
source "$venv/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e "$repo[dev,alfworld]"

if [[ ! -f "$repo/.env" ]]; then
  cp "$repo/.env.example" "$repo/.env"
  echo "Created .env from .env.example; fill local credentials if a later experiment needs them."
fi

if [[ ! -d "$data_root/json_2.1.1" ]]; then
  echo "ALFWorld data is missing: $data_root/json_2.1.1" >&2
  echo "Copy the dataset to this path or export ALFWORLD_DATA=/path/to/ALFWORLD_DATA." >&2
  exit 2
fi

cd "$repo"
python scripts/acl2027_experiment_handoff.py validate
python -m pytest -q -p no:cacheprovider \
  tests/test_acl2027_experiment_handoff.py \
  tests/test_acl2027_tracegraph_tg8_observable_subgoal_selector_v3.py \
  tests/test_acl2027_tracegraph_tg9_selector_v1.py

echo "WSL preparation complete. No experiment was launched."
