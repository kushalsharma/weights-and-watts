#!/bin/bash
# Sets up what episode 1 ran on, in this folder, on Linux with an NVIDIA card: ComfyUI at the same commit, in its own
# Python environment, with the PyTorch build we used. Safe to run again. Then get the models with get_models.py.
#
#   bash setup.sh
#
# Change the PyTorch build with TORCH_INDEX and TORCH, for example for an older driver:
#   TORCH_INDEX=https://download.pytorch.org/whl/cu126 TORCH="torch==2.14.1 torchvision" bash setup.sh
# and the Python it uses with PYTHON, for example PYTHON=python3.12 bash setup.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
COMMIT=$(python3 -c 'import json; print(json.load(open("models.json"))["comfyui"]["commit"])')
TORCH_INDEX=${TORCH_INDEX:-https://download.pytorch.org/whl/cu132}
TORCH=${TORCH:-torch==2.15.0 torchvision==0.29.2}
PYTHON=${PYTHON:-python3}

command -v nvidia-smi > /dev/null || { echo "No nvidia-smi here, so no NVIDIA driver to use."; exit 1; }
echo "card: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | head -1)"

if [ ! -d ComfyUI/.git ]; then
  git clone --quiet --filter=blob:none https://github.com/Comfy-Org/ComfyUI.git ComfyUI
fi
git -C ComfyUI fetch --quiet origin "$COMMIT" 2> /dev/null || true
git -C ComfyUI -c advice.detachedHead=false checkout --quiet "$COMMIT"
echo "ComfyUI at $(git -C ComfyUI log -1 --format='%h %cs')"

PY=ComfyUI/venv/bin/python
if ! "$PY" -m pip --version > /dev/null 2>&1; then
  rm -rf ComfyUI/venv
  "$PYTHON" -m venv ComfyUI/venv || { rm -rf ComfyUI/venv; echo "$PYTHON couldn't make an environment for ComfyUI. On Ubuntu or Debian, install python3-venv (sudo apt install python3-venv) and run this again, or name another Python with PYTHON=."; exit 1; }
fi
"$PY" -m pip install --quiet --upgrade pip
echo "PyTorch: $TORCH from $TORCH_INDEX"
# shellcheck disable=SC2086
"$PY" -m pip install --quiet --index-url "$TORCH_INDEX" $TORCH
"$PY" -m pip freeze | grep -E '^(torch|torchvision)==' > ComfyUI/venv/torch-pins.txt
"$PY" -m pip install --quiet -r ComfyUI/requirements.txt -c ComfyUI/venv/torch-pins.txt --extra-index-url "$TORCH_INDEX"
"$PY" -m pip install --quiet huggingface_hub -c ComfyUI/venv/torch-pins.txt
"$PY" - << 'EOF'
import torch
print("torch", torch.__version__, "CUDA", torch.version.cuda, "| card:", torch.cuda.get_device_name(0))
x = torch.randn(512, 512, device="cuda")
print("the card works:", bool(torch.allclose((x @ x).cpu(), x.cpu() @ x.cpu(), rtol=1e-3, atol=1e-2)))
EOF
echo
echo "Next:  $PY get_models.py h3-image      (or p-h3-image, or both)"
echo "Then:  $PY run_takes.py --comfy ComfyUI --model h3-image --prompt c-size-4mp"
