#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ffmpeg
fi

python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' \
  || { echo "python3 must be 3.12+" >&2; exit 1; }

python3 -m pip install --user -q pytest

chmod +x mirelo.py mix_music.py setup.sh
./setup.sh --agent openclaw
