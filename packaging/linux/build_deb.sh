#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; VERSION="0.17.0"
WHEEL="$(find "$ROOT/dist" -maxdepth 1 -name 'living_assistant-*.whl' | sort | tail -n1)"
[ -f "$WHEEL" ] || { echo "Build the wheel first." >&2; exit 2; }
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/share/living-assistant-release/dist" "$STAGE/usr/share/living-assistant-release/scripts" "$STAGE/usr/share/living-assistant-release/src/living_assistant" "$STAGE/usr/bin"
cp "$WHEEL" "$STAGE/usr/share/living-assistant-release/dist/"
cp "$ROOT/scripts/install.py" "$STAGE/usr/share/living-assistant-release/scripts/"
cp "$ROOT/src/living_assistant/release_manager.py" "$ROOT/src/living_assistant/__init__.py" "$STAGE/usr/share/living-assistant-release/src/living_assistant/"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: living-assistant-release
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.11), python3-venv
Maintainer: Living Assistant
Description: Living Assistant per-user release installer payload
EOF
cat > "$STAGE/usr/bin/living-assistant-install" <<'EOF'
#!/bin/sh
set -eu
ROOT=/usr/share/living-assistant-release
if [ "$#" -eq 0 ]; then
  WHEEL=$(find "$ROOT/dist" -name 'living_assistant-*.whl' | head -n1)
  exec python3 "$ROOT/scripts/install.py" install "$WHEEL"
fi
exec python3 "$ROOT/scripts/install.py" "$@"
EOF
chmod 0755 "$STAGE/usr/bin/living-assistant-install"
OUT="$ROOT/dist/living-assistant-release_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT"
echo "$OUT"
