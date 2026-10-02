#!/usr/bin/env bash
# Install the mirelo-sfx OpenClaw skill: writes SKILL.md, pointed at this clone,
# into the OpenClaw skills dir. It changes nothing else: no npm, no OpenClaw
# version or config changes, and it never reads your API key.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${OPENCLAW_SKILLS_DIR:-$HOME/.openclaw/skills}/mirelo-sfx"

command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' || { echo "python3 must be 3.12+" >&2; exit 1; }
for tool in ffmpeg ffprobe; do
    command -v "$tool" >/dev/null || { echo "$tool not found" >&2; exit 1; }
done

mkdir -p "$DEST"
escaped="${REPO//&/\\&}"
sed "s#~/mirelo-sfx-openclaw#${escaped//#/\\#}#g" "$REPO/SKILL.md" > "$DEST/SKILL.md.tmp"
mv "$DEST/SKILL.md.tmp" "$DEST/SKILL.md"
chmod +x "$REPO/mirelo.py"

echo "skill: $DEST/SKILL.md (uses $REPO/mirelo.py)"
if [ -z "${MIRELO_API_KEY:-}" ] && [ ! -f "$REPO/.env" ] && [ ! -f "$HOME/.config/mirelo/credentials" ]; then
    echo "next: cp .env.example .env && chmod 600 .env, then add your key"
fi
echo "check: python3 $REPO/mirelo.py doctor"
