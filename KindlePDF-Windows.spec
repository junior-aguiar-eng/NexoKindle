# -*- mode: python ; coding: utf-8 -*-
"""Two launchers sharing one Windows onedir bundle."""

a = Analysis(
    ['scripts/portable_app.py'],
    pathex=['src'],
    binaries=[],
    datas=[('.tmp/weasyprint-v70/onedir/weasyprint', 'weasyprint')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

gui = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KindlePDF',
    console=False,
    disable_windowed_traceback=False,
)
cli = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KindlePDF-CLI',
    console=True,
)
coll = COLLECT(
    gui,
    cli,
    a.binaries,
    a.datas,
    name='KindlePDF',
)
