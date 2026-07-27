#!/usr/bin/env bash
# Resume interrupted MMLU-Pro training runs (math_true & law_true)
# Trainer auto-detects runtime_state.json and resumes from last completed step.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

# Load API keys
set -a
source "${PROJECT_ROOT}/.env"
set +a

# Ensure openai_compatible backend picks up per-role env vars
export OPTIMIZER_OPENAI_COMPATIBLE_BASE_URL="${OPTIMIZER_OPENAI_COMPATIBLE_BASE_URL:-https://api.deepseek.com/v1}"
export OPTIMIZER_OPENAI_COMPATIBLE_API_KEY="${OPTIMIZER_OPENAI_COMPATIBLE_API_KEY:-}"
export OPTIMIZER_OPENAI_COMPATIBLE_MODEL="${OPTIMIZER_OPENAI_COMPATIBLE_MODEL:-deepseek-v4-flash}"
export TARGET_OPENAI_COMPATIBLE_BASE_URL="${TARGET_OPENAI_COMPATIBLE_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
export TARGET_OPENAI_COMPATIBLE_API_KEY="${TARGET_OPENAI_COMPATIBLE_API_KEY:-}"
export TARGET_OPENAI_COMPATIBLE_MODEL="${TARGET_OPENAI_COMPATIBLE_MODEL:-qwen-flash}"

cd "${PROJECT_ROOT}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

echo "============================================================"
echo "  SkillOpt — Resume MMLU-Pro Training"
echo "============================================================"
echo "  Optimizer: ${OPTIMIZER_OPENAI_COMPATIBLE_MODEL}"
echo "  Target:    ${TARGET_OPENAI_COMPATIBLE_MODEL}"
echo "  Timestamp: ${TIMESTAMP}"
echo "============================================================"

# ── math_true ──────────────────────────────────────────────────
echo ""
echo ">>> [1/2] Resuming mmlupro_math_true ..."
python scripts/train.py \
  --config configs/mmlupro/default.yaml \
  --cfg-options \
    env.split_dir=data/mmlupro_math \
    train.train_size=800 \
    env.out_root="${PROJECT_ROOT}/outputs/mmlupro_math_true" \
  2>&1 | tee -a "${PROJECT_ROOT}/logs/mmlupro_math_true_${TIMESTAMP}_resume.log"

echo ""
echo ">>> [1/2] math_true done!"
echo ""

# ── law_true ───────────────────────────────────────────────────
echo ">>> [2/2] Resuming mmlupro_law_true ..."
python scripts/train.py \
  --config configs/mmlupro/default.yaml \
  --cfg-options \
    env.split_dir=data/mmlupro_law \
    train.train_size=660 \
    env.out_root="${PROJECT_ROOT}/outputs/mmlupro_law_true" \
  2>&1 | tee -a "${PROJECT_ROOT}/logs/mmlupro_law_true_${TIMESTAMP}_resume.log"

echo ""
echo ">>> [2/2] law_true done!"
echo ""
echo "============================================================"
echo "  Both experiments completed!"
echo "  math: ${PROJECT_ROOT}/outputs/mmlupro_math_true"
echo "  law:  ${PROJECT_ROOT}/outputs/mmlupro_law_true"
echo "============================================================"
