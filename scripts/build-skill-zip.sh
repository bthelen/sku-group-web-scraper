#!/usr/bin/env bash
# Build a self-contained skill zip for upload to hosted AI harnesses.
# Usage: bash scripts/build-skill-zip.sh
# Output: dist/gcp-sku-groups.zip

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$(mktemp -d)"
DIST_DIR="$REPO_ROOT/dist"
ZIP_NAME="gcp-sku-groups.zip"

cleanup() { rm -rf "$BUILD_DIR"; }
trap cleanup EXIT

echo "Building wheel..."
python -m pip wheel "$REPO_ROOT" --no-deps -w "$BUILD_DIR/wheels/" -q

WHEEL=$(ls "$BUILD_DIR/wheels/"*.whl)
WHEEL_NAME=$(basename "$WHEEL")

echo "Assembling skill package..."

# setup.sh — installs the wheel and its PyPI dependencies
cat > "$BUILD_DIR/setup.sh" <<'EOF'
#!/usr/bin/env bash
# Install the sku-scraper CLI bundled with this skill package.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
pip install "$DIR/wheels/"*.whl
echo "sku-scraper installed. Run 'sku-scraper --help' to verify."
EOF
chmod +x "$BUILD_DIR/setup.sh"

# SKILL.md — copy from repo, replacing the setup section for zip users
sed 's|pip install -e \.|bash setup.sh|g' \
    "$REPO_ROOT/skills/gcp-sku-groups/SKILL.md" \
    > "$BUILD_DIR/SKILL.md"

mkdir -p "$DIST_DIR"
(cd "$BUILD_DIR" && zip -r "$DIST_DIR/$ZIP_NAME" SKILL.md setup.sh wheels/ -q)

echo "Created: dist/$ZIP_NAME"
echo "  SKILL.md"
echo "  setup.sh"
echo "  wheels/$WHEEL_NAME"
