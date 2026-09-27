#!/usr/bin/env bash
set -e

echo "Updating external components is manual. For a given component:"
echo "1. Rename the old directory (e.g., mv external-components/browser-use external-components/browser-use.old)"
echo "2. git clone <upstream_url> external-components/browser-use"
echo "3. cd external-components/browser-use && git checkout <desired_commit>"
echo "4. rm -rf .git"
echo "5. Update docs/EXTERNAL_COMPONENTS.md with the new commit hash."
echo "6. Run tests to ensure compatibility."
