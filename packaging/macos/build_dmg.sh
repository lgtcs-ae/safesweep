#!/usr/bin/env bash
set -euo pipefail

APP_NAME="SafeSweep"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RELEASE_DIR="${ROOT_DIR}/release/macos"
SPEC_FILE="${ROOT_DIR}/packaging/macos/safesweep.spec"
APP_PATH="${ROOT_DIR}/dist/${APP_NAME}.app"
DMG_STAGING="${RELEASE_DIR}/dmg-staging"
DMG_PATH="${RELEASE_DIR}/${APP_NAME}-macOS.dmg"

cd "${ROOT_DIR}"

if ! python3 -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller is not installed."
  echo "Install it with: python3 -m pip install pyinstaller"
  exit 1
fi

rm -rf build dist "${RELEASE_DIR}"
mkdir -p "${DMG_STAGING}"

python3 packaging/macos/create_icon.py

python3 -m PyInstaller --clean --noconfirm "${SPEC_FILE}"

if [[ ! -d "${APP_PATH}" ]]; then
  echo "Expected app was not created: ${APP_PATH}"
  exit 1
fi

cp -R "${APP_PATH}" "${DMG_STAGING}/"
ln -s /Applications "${DMG_STAGING}/Applications"

hdiutil create \
  -volname "${APP_NAME}" \
  -srcfolder "${DMG_STAGING}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}"

echo "Created ${APP_PATH}"
echo "Created ${DMG_PATH}"
