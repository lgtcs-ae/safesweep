# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path.cwd()


a = Analysis(
    [str(ROOT / "packaging/macos/SafeSweepLauncher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "templates"), "templates"),
        (str(ROOT / "static"), "static"),
    ],
    hiddenimports=["jinja2"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SafeSweep",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SafeSweep",
)

app = BUNDLE(
    coll,
    name="SafeSweep.app",
    icon=str(ROOT / "packaging/macos/SafeSweep.icns"),
    bundle_identifier="ae.lgtcs.safesweep",
    info_plist={
        "CFBundleName": "SafeSweep",
        "CFBundleDisplayName": "SafeSweep",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
    },
)
