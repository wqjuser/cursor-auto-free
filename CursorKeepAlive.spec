# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# 确定是否是 Windows 系统
is_windows = sys.platform.startswith('win')
is_mac = sys.platform == 'darwin'

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
        '_tkinter',  # 添加tkinter相关依赖
        'tkinter.ttk',
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

# 命令行版本EXE/Unix可执行文件
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
    argv_emulation=is_mac,  # Mac需要argv模拟
    target_arch=target_arch,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)

# UI版本EXE/Unix可执行文件
exe_ui = EXE(
    pyz_ui,
    b.scripts,
    b.binaries,
    b.datas,
    [],
    name='CursorPro',
    debug=True,  # 启用调试
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True if is_mac else False,  # Mac版本显示控制台以查看错误
    disable_windowed_traceback=False,
    argv_emulation=is_mac,
    target_arch=target_arch,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)

# 如果在 Mac 上构建
if is_mac:
    # Info.plist内容
    info_plist = {
        'CFBundleIdentifier': 'com.cursor.pro',
        'CFBundleName': 'CursorPro',
        'CFBundleDisplayName': 'CursorPro',
        'CFBundleExecutable': 'CursorPro',
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': '1.0.0',
        'LSBackgroundOnly': False,
        'LSMinimumSystemVersion': '10.13.0',  # 降低最低系统要求
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'NSAppleEventsUsageDescription': 'App requires access to run properly',
        'NSAppleScriptEnabled': True,
    }
    
    # CLI版本的bundle
    app_cli = BUNDLE(
        exe_cli,
        name='CursorPro_CLI.app',
        icon=None,
        bundle_identifier='com.cursor.pro.cli',
        info_plist={
            **info_plist,
            'CFBundleName': 'CursorPro CLI',
            'CFBundleDisplayName': 'CursorPro CLI',
            'CFBundleExecutable': 'CursorPro_CLI',
            'LSUIElement': True,  # 允许在终端中运行
        }
    )
    
    # UI版本的bundle
    app_ui = BUNDLE(
        exe_ui,
        name='CursorPro.app',
        icon=None,
        bundle_identifier='com.cursor.pro.ui',
        info_plist={
            **info_plist,
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,
        }
    )