#!/usr/bin/env bash
set -euo pipefail
exec "$(cd "$(dirname "$0")" && pwd)/install_release_macos.sh" "$@"
