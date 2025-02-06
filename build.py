import warnings
import os
import platform
import subprocess
import time
import threading
from PIL import Image

# Ignore specific SyntaxWarning
warnings.filterwarnings("ignore", category=SyntaxWarning, module="DrissionPage")

CURSOR_LOGO = """
   ██████╗██╗   ██╗██████╗ ███████╗ ██████╗ ██████╗ 
  ██╔════╝██║   ██║██╔══██╗██╔════╝██╔═══██╗██╔══██╗
  ██║     ██║   ██║██████╔╝███████╗██║   ██║██████╔╝
  ██║     ██║   ██║██╔══██╗╚════██║██║   ██║██╔══██╗
  ╚██████╗╚██████╔╝██║  ██║███████║╚██████╔╝██║  ██║
   ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝
"""


class LoadingAnimation:
    def __init__(self):
        self.is_running = False
        self.animation_thread = None

    def start(self, message="Building"):
        self.is_running = True
        self.animation_thread = threading.Thread(target=self._animate, args=(message,))
        self.animation_thread.start()

    def stop(self):
        self.is_running = False
        if self.animation_thread:
            self.animation_thread.join()
        print("\r" + " " * 70 + "\r", end="", flush=True)  # Clear the line

    def _animate(self, message):
        animation = "|/-\\"
        idx = 0
        while self.is_running:
            print(f"\r{message} {animation[idx % len(animation)]}", end="", flush=True)
            idx += 1
            time.sleep(0.1)


def print_logo():
    print("\033[96m" + CURSOR_LOGO + "\033[0m")
    print("\033[93m" + "Building Cursor Keep Alive...".center(56) + "\033[0m\n")


def progress_bar(progress, total, prefix="", length=50):
    filled = int(length * progress // total)
    bar = "█" * filled + "░" * (length - filled)
    percent = f"{100 * progress / total:.1f}"
    print(f"\r{prefix} |{bar}| {percent}% Complete", end="", flush=True)
    if progress == total:
        print()


def simulate_progress(message, duration=1.0, steps=20):
    print(f"\033[94m{message}\033[0m")
    for i in range(steps + 1):
        time.sleep(duration / steps)
        progress_bar(i, steps, prefix="Progress:", length=40)


def filter_output(output):
    """ImportantMessage"""
    if not output:
        return ""
    important_lines = []
    for line in output.split("\n"):
        # Only keep lines containing specific keywords
        if any(
            keyword in line.lower()
            for keyword in ["error:", "failed:", "completed", "directory:"]
        ):
            important_lines.append(line)
    return "\n".join(important_lines)


def convert_png_to_icns(png_path, output_path):
    """将 PNG 转换为 ICNS 格式"""
    try:
        import os
        
        # 创建临时图标集目录
        iconset_path = output_path.replace('.icns', '.iconset')
        os.makedirs(iconset_path, exist_ok=True)
        
        # 需要生成的尺寸列表
        sizes = [16, 32, 64, 128, 256, 512, 1024]
        
        # 打开源图片
        img = Image.open(png_path)
        
        # 生成不同尺寸
        for size in sizes:
            # 普通版本
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(os.path.join(iconset_path, f'icon_{size}x{size}.png'))
            
            # Retina 版本 (2x)
            if size <= 512:
                retina_size = size * 2
                resized = img.resize((retina_size, retina_size), Image.Resampling.LANCZOS)
                resized.save(os.path.join(iconset_path, f'icon_{size}x{size}@2x.png'))
        
        # 使用 iconutil 将图标集转换为 icns
        os.system(f'iconutil -c icns {iconset_path}')
        
        # 清理临时文件
        import shutil
        shutil.rmtree(iconset_path)
        
        return True
    except Exception as e:
        print(f"\033[93mWarning: Failed to convert PNG to ICNS: {e}\033[0m")
        return False


def build():
    # Clear screen
    os.system("cls" if platform.system().lower() == "windows" else "clear")

    # Print logo
    print_logo()

    system = platform.system().lower()
    spec_file = os.path.join("CursorKeepAlive.spec")

    # if system not in ["darwin", "windows"]:
    #     print(f"\033[91mUnsupported operating system: {system}\033[0m")
    #     return

    output_dir = f"dist/{system if system != 'darwin' else 'mac'}"

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    simulate_progress("Creating output directory...", 0.5)

    # 使用 spec 文件构建
    pyinstaller_command = [
        "pyinstaller",
        spec_file,
        "--distpath", output_dir,
        "--workpath", f"build/{system}",
        "--noconfirm",
    ]

    # Mac 特定的环境变量设置
    if system == "darwin":
        build_env = os.environ.copy()
        build_env['DYLD_LIBRARY_PATH'] = ''  # 清除动态库路径
        build_env['CURL_CA_BUNDLE'] = ''     # 清除 SSL 证书路径
        build_env['REQUESTS_CA_BUNDLE'] = '' # 清除 requests 证书路径
    else:
        build_env = None
    
    loading = LoadingAnimation()
    try:
        simulate_progress("Building CLI and UI versions...", 2.0)
        loading.start("Building in progress")
        
        process = subprocess.Popen(
            pyinstaller_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='ignore',
            env=build_env  # 使用修改后的环境变量
        )
        
        stdout, stderr = process.communicate()
        loading.stop()

        if process.returncode != 0:
            print(f"\033[91mBuild failed with error code {process.returncode}\033[0m")
            if stderr:
                print("\033[91mError Details:\033[0m")
                print(stderr)
            return

        if stderr:
            filtered_errors = [
                line for line in stderr.split("\n")
                if any(keyword in line.lower() 
                      for keyword in ["error:", "failed:", "completed", "directory:"])
            ]
            if filtered_errors:
                print("\033[93mBuild Warnings/Errors:\033[0m")
                print("\n".join(filtered_errors))

    except Exception as e:
        loading.stop()
        print(f"\033[91mBuild failed: {str(e)}\033[0m")
        return
    finally:
        loading.stop()

    # 复制配置文件
    try:
        # Copy config file
        if os.path.exists("config.ini.example"):
            simulate_progress("Copying configuration files...", 0.5)
            if system == "windows":
                # 为CLI版本复制
                config_src = os.path.abspath("config.ini.example")
                config_dst_cli = os.path.join(output_dir, "CursorPro_CLI", "config.ini")
                os.makedirs(os.path.dirname(config_dst_cli), exist_ok=True)
                
                # 为UI版本复制
                config_dst_ui = os.path.join(output_dir, "CursorPro", "config.ini")
                os.makedirs(os.path.dirname(config_dst_ui), exist_ok=True)
                
                try:
                    import shutil
                    shutil.copy2(config_src, config_dst_cli)
                    shutil.copy2(config_src, config_dst_ui)
                except Exception as e:
                    print(f"\033[93mWarning: Failed to copy config files: {e}\033[0m")
            elif system == "darwin":
                config_src = os.path.abspath("config.ini.example")
                # 为CLI版本复制
                config_dst_cli = os.path.join(output_dir, "CursorPro_CLI.app", "Contents", "MacOS", "config.ini")
                os.makedirs(os.path.dirname(config_dst_cli), exist_ok=True)
                
                # 为UI版本复制
                config_dst_ui = os.path.join(output_dir, "CursorPro.app", "Contents", "MacOS", "config.ini")
                os.makedirs(os.path.dirname(config_dst_ui), exist_ok=True)
                
                try:
                    import shutil
                    shutil.copy2(config_src, config_dst_cli)
                    shutil.copy2(config_src, config_dst_ui)
                except Exception as e:
                    print(f"\033[93mWarning: Failed to copy config files: {e}\033[0m")

        # Copy .env.example file
        if os.path.exists(".env.example"):
            simulate_progress("Copying environment files...", 0.5)
            if system == "windows":
                env_src = os.path.abspath(".env.example")
                
                # 为CLI版本复制
                env_dst_cli = os.path.join(output_dir, "CursorPro_CLI", ".env")
                # 为UI版本复制
                env_dst_ui = os.path.join(output_dir, "CursorPro", ".env")
                
                try:
                    import shutil
                    shutil.copy2(env_src, env_dst_cli)
                    shutil.copy2(env_src, env_dst_ui)
                except Exception as e:
                    print(f"\033[93mWarning: Failed to copy env files: {e}\033[0m")
            elif system == "darwin":
                env_src = os.path.abspath(".env.example")
                
                # 为CLI版本复制
                env_dst_cli = os.path.join(output_dir, "CursorPro_CLI.app", "Contents", "MacOS", ".env")
                # 为UI版本复制
                env_dst_ui = os.path.join(output_dir, "CursorPro.app", "Contents", "MacOS", ".env")
                
                try:
                    import shutil
                    shutil.copy2(env_src, env_dst_cli)
                    shutil.copy2(env_src, env_dst_ui)
                except Exception as e:
                    print(f"\033[93mWarning: Failed to copy env files: {e}\033[0m")

    except Exception as e:
        print(f"\033[93mWarning: File copying failed: {e}\033[0m")

    # 在构建完成后添加执行权限和配置（仅Mac）
    if system == "darwin":
        try:
            simulate_progress("Configuring Mac application...", 0.5)
            
            # 设置路径
            cli_path = os.path.join(output_dir, "CursorPro_CLI.app", "Contents", "MacOS", "CursorPro_CLI")
            ui_path = os.path.join(output_dir, "CursorPro.app", "Contents", "MacOS", "CursorPro")
            
            # 处理图标
            icon_png = os.path.abspath("assets/icon.png")  # PNG 源文件路径
            icon_icns = os.path.abspath("assets/icon.icns")  # 转换后的 ICNS 文件路径
            icon_dst = os.path.join(output_dir, "CursorPro.app", "Contents", "Resources", "icon.icns")
            
            # 确保 Resources 目录存在
            os.makedirs(os.path.dirname(icon_dst), exist_ok=True)
            
            # 如果存在 PNG 文件，尝试转换
            if os.path.exists(icon_png):
                print("\033[94mConverting PNG to ICNS format...\033[0m")
                if convert_png_to_icns(icon_png, icon_icns):
                    print("\033[92mPNG conversion successful\033[0m")
                else:
                    print("\033[93mWarning: PNG conversion failed\033[0m")
            
            # 复制图标文件
            if os.path.exists(icon_icns):
                import shutil
                shutil.copy2(icon_icns, icon_dst)
                print("\033[92mIcon file copied successfully\033[0m")
            else:
                print("\033[93mWarning: Icon file not found\033[0m")
            
            # Info.plist 中添加图标配置
            info_plist_content = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>CursorPro</string>
    <key>CFBundleExecutable</key>
    <string>CursorPro</string>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.cursor.pro</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>CursorPro</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
    <key>LSBackgroundOnly</key>
    <false/>
    <key>LSUIElement</key>
    <false/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>This app requires access to run administrative tasks.</string>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>CursorPro Document</string>
            <key>CFBundleTypeRole</key>
            <string>Editor</string>
            <key>LSHandlerRank</key>
            <string>Owner</string>
        </dict>
    </array>
</dict>
</plist>'''
            
            # 写入 Info.plist
            info_plist_path = os.path.join(output_dir, "CursorPro.app", "Contents", "Info.plist")
            with open(info_plist_path, "w") as f:
                f.write(info_plist_content)
            
            # 创建启动脚本 - 包装原始可执行文件
            launcher_script = '''#!/bin/bash
cd "$(dirname "$0")"
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export PYTHONPATH="$(dirname "$0")"
export PYTHONHOME="$(dirname "$0")/Python"
export DYLD_LIBRARY_PATH="$(dirname "$0")"
export DYLD_FRAMEWORK_PATH="$(dirname "$0")"
export SSL_CERT_FILE=""
export REQUESTS_CA_BUNDLE=""
export PYTHONUNBUFFERED=1

# 启动应用程序
exec "$(dirname "$0")/CursorPro_original" "$@"
'''
            
            # 重命名原始可执行文件并创建启动脚本
            original_exe = os.path.join(output_dir, "CursorPro.app", "Contents", "MacOS", "CursorPro")
            if os.path.exists(original_exe):
                os.rename(original_exe, original_exe + "_original")
                with open(original_exe, "w") as f:
                    f.write(launcher_script)
                os.chmod(original_exe, 0o755)
            
            # 创建环境变量文件
            env_content = '''
CURL_CA_BUNDLE=
REQUESTS_CA_BUNDLE=
PYTHONWARNINGS=ignore:NotOpenSSLWarning
PYTHONUNBUFFERED=1
DISPLAY=:0
'''
            for app_path in [cli_path, ui_path]:
                env_file = os.path.join(os.path.dirname(app_path), ".env")
                with open(env_file, "w") as f:
                    f.write(env_content)
                
            print("\033[92mMac configuration completed\033[0m")
        except Exception as e:
            print(f"\033[93mWarning: Failed to configure Mac application: {e}\033[0m")
    
    print(f"\n\033[92mBuild completed successfully!\033[0m")
    if system == "darwin":
        print("\033[93mFor debugging, run the following command:\033[0m")
        print(f"\033[93m{os.path.join(output_dir, 'CursorPro.app', 'Contents', 'MacOS', 'CursorPro')}\033[0m")
    print(f"\033[92mCLI version: {os.path.join(output_dir, 'CursorPro_CLI')}\033[0m")
    print(f"\033[92mUI version: {os.path.join(output_dir, 'CursorPro')}\033[0m")


if __name__ == "__main__":
    build()
