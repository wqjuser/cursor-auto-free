import warnings
import os
import platform
import subprocess
import time
import threading

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

    loading = LoadingAnimation()
    try:
        simulate_progress("Building CLI and UI versions...", 2.0)
        loading.start("Building in progress")
        
        process = subprocess.Popen(
            pyinstaller_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='ignore'
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

    # 在构建完成后添加执行权限（仅Mac）
    if system == "darwin":
        try:
            simulate_progress("Setting permissions...", 0.5)
            cli_path = os.path.join(output_dir, "CursorPro_CLI.app", "Contents", "MacOS", "CursorPro_CLI")
            ui_path = os.path.join(output_dir, "CursorPro.app", "Contents", "MacOS", "CursorPro")
            
            if os.path.exists(cli_path):
                os.chmod(cli_path, 0o755)
            if os.path.exists(ui_path):
                os.chmod(ui_path, 0o755)
                
            print("\033[92mPermissions set successfully\033[0m")
        except Exception as e:
            print(f"\033[93mWarning: Failed to set permissions: {e}\033[0m")
    
    print(f"\n\033[92mBuild completed successfully!\033[0m")
    if system == "darwin":
        print("\033[93mFor debugging, run the following command:\033[0m")
        print(f"\033[93m{os.path.join(output_dir, 'CursorPro.app', 'Contents', 'MacOS', 'CursorPro')}\033[0m")
    print(f"\033[92mCLI version: {os.path.join(output_dir, 'CursorPro_CLI')}\033[0m")
    print(f"\033[92mUI version: {os.path.join(output_dir, 'CursorPro')}\033[0m")


if __name__ == "__main__":
    build()
