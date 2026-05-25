import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Bundle static files
datas = [
    ('simmer/static', 'simmer/static'),
]
datas += collect_data_files('aiohttp')

hidden_imports = (
    collect_submodules('aiohttp') +
    collect_submodules('Quartz') +
    collect_submodules('AppKit') +
    collect_submodules('Foundation') +
    ['_multiprocessing', 'multiprocessing.resource_tracker', 'multiprocessing.synchronize']
)

a = Analysis(
    ['simmer/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='simmer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
