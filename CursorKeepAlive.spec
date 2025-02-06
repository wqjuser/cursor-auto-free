# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# 确定是否是 Windows 系统
is_windows = sys.platform.startswith('win')

# 命令行版本
a = Analysis(
    ['cursor_pro_keep_alive.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('turnstilePatch', 'turnstilePatch'),
        ('cursor_auth_manager.py', '.'),
        ('patch_cursor_get_machine_id.py', '.')
    ],
    hiddenimports=[
        'cursor_auth_manager',
        'psutil',
        'DrissionPage',
        'colorama',
        'exit_cursor',
        'browser_utils',
        'get_email_code',
        'logo',
        'config',
        'patch_cursor_get_machine_id',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# UI版本
b = Analysis(
    ['cursor_pro_ui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('turnstilePatch', 'turnstilePatch'),
        ('cursor_auth_manager.py', '.'),
        ('patch_cursor_get_machine_id.py', '.')
    ],
    hiddenimports=[
        'cursor_auth_manager',
        'psutil',
        'DrissionPage',
        'colorama',
        'exit_cursor',
        'browser_utils',
        'get_email_code',
        'logo',
        'config',
        'patch_cursor_get_machine_id',
        'tkinter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_cli = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
pyz_ui = PYZ(b.pure, b.zipped_data, cipher=block_cipher)

target_arch = os.environ.get('TARGET_ARCH', None)

# 命令行版本EXE
exe_cli = EXE(
    pyz_cli,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CursorPro_CLI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=target_arch,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)

# UI版本EXE
exe_ui = EXE(
    pyz_ui,
    b.scripts,
    b.binaries,
    b.datas,
    [],
    name='CursorPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # UI版本不需要控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=target_arch,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)

# 如果在 Mac 上构建
if sys.platform == 'darwin':
    app_cli = BUNDLE(
        exe_cli,
        name='CursorPro_CLI.app',
        icon=None,
        bundle_identifier=None,
    )
    app_ui = BUNDLE(
        exe_ui,
        name='CursorPro.app',
        icon=None,
        bundle_identifier=None,
    )