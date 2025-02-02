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
        simulate_progress("Running PyInstaller...", 2.0)
        loading.start("Building in progress")
        
        # 修改这里，添加编码设置
        process = subprocess.Popen(
            pyinstaller_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',  # 指定编码
            errors='ignore'    # 忽略无法解码的字符
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

    # 修改文件复制部分
    try:
        # Copy config file
        if os.path.exists("config.ini.example"):
            simulate_progress("Copying configuration file...", 0.5)
            if system == "windows":
                config_src = os.path.abspath("config.ini.example")
                config_dst = os.path.join(output_dir, "config.ini")
                try:
                    import shutil
                    shutil.copy2(config_src, config_dst)
                except Exception as e:
                    print(f"\033[93mWarning: Failed to copy config file: {e}\033[0m")

        # Copy .env.example file
        if os.path.exists(".env.example"):
            simulate_progress("Copying environment file...", 0.5)
            if system == "windows":
                env_src = os.path.abspath(".env.example")
                env_dst = os.path.join(output_dir, ".env")
                try:
                    import shutil
                    shutil.copy2(env_src, env_dst)
                except Exception as e:
                    print(f"\033[93mWarning: Failed to copy env file: {e}\033[0m")

    except Exception as e:
        print(f"\033[93mWarning: File copying failed: {e}\033[0m")

    print(f"\n\033[92mBuild completed successfully! Output directory: {output_dir}\033[0m")


if __name__ == "__main__":
    build()
