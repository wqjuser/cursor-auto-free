# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# 确定是否是 Windows 系统
is_windows = sys.platform.startswith('win')

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
        'python-dotenv',
        'exit_cursor',
        'browser_utils',
        'get_email_code',
        'logo',
        'config',
        'patch_cursor_get_machine_id',
        # scapy 相关依赖
        'scapy',
        'scapy.arch',
        'scapy.arch.common',
        'scapy.arch.unix',
        'scapy.base_classes',
        'scapy.compat',
        'scapy.config',
        'scapy.consts',
        'scapy.data',
        'scapy.error',
        'scapy.fields',
        'scapy.interfaces',
        'scapy.libs',
        'scapy.libs.winpcapy',
        'scapy.packet',
        'scapy.utils',
        'scapy.utils6',
        'scapy.volatile'
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

# 添加 scapy 数据文件
import scapy
scapy_path = os.path.dirname(scapy.__file__)
a.datas += Tree(scapy_path, prefix='scapy')

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

target_arch = os.environ.get('TARGET_ARCH', None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CursorPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 保持控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,  # Windows 不需要 argv 模拟
    target_arch=target_arch,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)

# 如果在 Mac 上构建
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='CursorPro.app',
        icon=None,
        bundle_identifier=None,
    )
