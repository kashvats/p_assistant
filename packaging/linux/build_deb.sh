#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="$(sed -n 's/^__version__ = "\([^"]*\)"/\1/p' "$ROOT/src/living_assistant/__init__.py")"
[ -n "$VERSION" ] || { echo "Could not determine version." >&2; exit 2; }
WHEEL="$(find "$ROOT/dist" -maxdepth 1 -name 'living_assistant-*.whl' | sort | tail -n1)"
[ -f "$WHEEL" ] || { echo "Build the wheel first." >&2; exit 2; }
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/share/living-assistant-release/dist" "$STAGE/usr/share/living-assistant-release/scripts" "$STAGE/usr/share/living-assistant-release/src/living_assistant" "$STAGE/usr/bin"
cp "$WHEEL" "$STAGE/usr/share/living-assistant-release/dist/"
cp "$ROOT/SHA256SUMS.txt" "$STAGE/usr/share/living-assistant-release/SHA256SUMS.txt"
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
  NAME=$(basename "$WHEEL")
  SHA=$(awk -v name="$NAME" '$2 ~ ("(^|/)" name "$") {print $1; exit}' "$ROOT/SHA256SUMS.txt")
  [ -n "$SHA" ] || { echo "Checksum entry missing for $NAME" >&2; exit 4; }
  exec python3 "$ROOT/scripts/install.py" install "$WHEEL" --sha256 "$SHA"
fi
exec python3 "$ROOT/scripts/install.py" "$@"
EOF
chmod 0755 "$STAGE/usr/bin/living-assistant-install"
OUT="$ROOT/dist/living-assistant-release_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT"
echo "$OUT"
