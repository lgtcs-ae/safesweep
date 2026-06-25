# SafeSweep macOS Packaging

This folder contains the first unsigned macOS packaging path for SafeSweep.

## What It Builds

- `dist/SafeSweep.app`
- `release/macos/SafeSweep-macOS.dmg`

The app starts the local SafeSweep backend and opens the browser UI at:

```text
http://127.0.0.1:8765
```

For smoke testing without opening a browser:

```bash
SAFESWEEP_PORT=8766 SAFESWEEP_NO_BROWSER=1 dist/SafeSweep.app/Contents/MacOS/SafeSweep
```

## Build Locally

From the repository root:

```bash
python3 -m pip install pyinstaller pillow
bash packaging/macos/build_dmg.sh
```

The build script creates `packaging/macos/SafeSweep.icns` from generated icon assets before
running PyInstaller.

## Notes

- This first DMG is unsigned.
- macOS may show an unidentified developer warning.
- Public distribution should eventually use Apple Developer ID signing and notarization.
- SafeSweep still runs locally and binds only to `127.0.0.1`.
