#!/bin/bash
set -e

VERSION=${1:-"1.0.0"}
DIST_DIR="dist"
APP_NAME="SerialMonitor"
DMG_NAME="${APP_NAME}-${VERSION}-macOS-arm64.dmg"

echo "Building ${APP_NAME} v${VERSION}..."

# Build .app (ARM64 native)
arch -arm64 .venv/bin/pyinstaller serial_monitor.spec --noconfirm

# Create DMG
echo "Creating DMG..."
mkdir -p dmg_staging
cp -r "${DIST_DIR}/${APP_NAME}.app" dmg_staging/
ln -sf /Applications dmg_staging/Applications

hdiutil create \
  -volname "${APP_NAME}" \
  -srcfolder dmg_staging \
  -ov \
  -format UDZO \
  "${DIST_DIR}/${DMG_NAME}"

rm -rf dmg_staging
echo "Done: ${DIST_DIR}/${DMG_NAME} ($(du -sh "${DIST_DIR}/${DMG_NAME}" | cut -f1))"
