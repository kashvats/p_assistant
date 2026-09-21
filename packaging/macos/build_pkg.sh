#!/usr/bin/env bash
set -euo pipefail
[ "$(uname -s)" = Darwin ] || { echo "pkgbuild must run on macOS." >&2; exit 2; }
command -v pkgbuild >/dev/null || { echo "pkgbuild not found." >&2; exit 2; }
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="$(sed -n 's/^__version__ = "\([^"]*\)"/\1/p' "$ROOT/src/living_assistant/__init__.py")"
[ -n "$VERSION" ] || { echo "Could not determine version." >&2; exit 2; }
WHEEL="$(find "$ROOT/dist" -maxdepth 1 -name 'living_assistant-*.whl' | sort | tail -n1)"
[ -f "$WHEEL" ] || { echo "Build the wheel first." >&2; exit 2; }
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
BASE="$STAGE/Library/Application Support/LivingAssistantRelease"
mkdir -p "$BASE/dist" "$BASE/scripts" "$BASE/src/living_assistant" "$STAGE/usr/local/bin"
cp "$WHEEL" "$BASE/dist/"; cp "$ROOT/SHA256SUMS.txt" "$BASE/SHA256SUMS.txt"; cp "$ROOT/scripts/install.py" "$BASE/scripts/"; cp "$ROOT/src/living_assistant/release_manager.py" "$ROOT/src/living_assistant/__init__.py" "$BASE/src/living_assistant/"
cat > "$STAGE/usr/local/bin/living-assistant-install" <<'EOF'
#!/bin/sh
set -eu
ROOT='/Library/Application Support/LivingAssistantRelease'
command -v python3 >/dev/null || { echo 'Python 3.11+ is required.' >&2; exit 2; }
if [ "$#" -eq 0 ]; then
  WHEEL=$(find "$ROOT/dist" -name 'living_assistant-*.whl' | head -n1)
  NAME=$(basename "$WHEEL")
  SHA=$(awk -v name="$NAME" '$2 ~ ("(^|/)" name "$") {print $1; exit}' "$ROOT/SHA256SUMS.txt")
  [ -n "$SHA" ] || { echo "Checksum entry missing for $NAME" >&2; exit 4; }
  exec python3 "$ROOT/scripts/install.py" install "$WHEEL" --sha256 "$SHA"
fi
exec python3 "$ROOT/scripts/install.py" "$@"
EOF
chmod 0755 "$STAGE/usr/local/bin/living-assistant-install"
pkgbuild --root "$STAGE" --identifier com.livingassistant.release --version "$VERSION" "$ROOT/dist/LivingAssistant-$VERSION.pkg"
echo "Unsigned package built. Sign/notarize on the release Mac before distribution."
