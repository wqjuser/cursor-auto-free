import ctypes
import os
import subprocess
import sys
from exit_cursor import ExitCursor
# 禁用不必要的日志输出
os.environ["PYTHONVERBOSE"] = "0"
os.environ["PYINSTALLER_VERBOSE"] = "0"
os.environ["PYTHONWARNINGS"] = "ignore"
import time
import random
from cursor_auth_manager import CursorAuthManager
from logger import logging
from browser_utils import BrowserManager
from get_email_code import EmailVerificationHandler
from logo import print_logo
from config import Config
from datetime import datetime
import uuid


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() if os.name == 'nt' else os.geteuid() == 0
    except Exception as exception:
        return False


def request_admin():
    script_path = os.path.abspath(__file__)

    if os.name == 'nt':  # Windows
        if not is_admin():
            try:
                if getattr(sys, 'frozen', False):
                    # 如果是打包后的可执行文件
                    executable = sys.executable
                    ret = ctypes.windll.shell32.ShellExecuteW(
                        None, 
                        "runas",
                        executable,
                        None,  # 打包后的exe不需要额外参数
                        None,
                        1  # SW_NORMAL
                    )
                else:
                    # 如果是 Python 脚本
                    ret = ctypes.windll.shell32.ShellExecuteW(
                        None, 
                        "runas",
                        sys.executable,
                        script_path,  # Python脚本需要作为参数传入
                        None,
                        1  # SW_NORMAL
                    )
                
                if ret <= 32:  # ShellExecute 返回值小于等于32表示失败
                    raise Exception(f"ShellExecute failed with code {ret}")
                sys.exit(0)  # 成功启动新进程后退出当前进程
            except Exception as e:
                print(f"请求管理员权限失败: {e}")
                print("请右键以管理员身份运行此程序")
                sys.exit(1)
    else:  # macOS/Linux
        if not is_admin():
            print("\n需要管理员权限来运行此程序。")
            print(f"请使用以下命令运行：\nsudo 脚本路径")
            sys.exit(1)


def save_screenshot(tab, prefix="turnstile"):
    """保存截图
    Args:
        tab: 浏览器标签页对象
        prefix: 文件名前缀
    Returns:
        str: 截图文件路径
    """
    try:
        # 创建 screenshots 目录
        screenshot_dir = "screenshots"
        if not os.path.exists(screenshot_dir):
            os.makedirs(screenshot_dir)

        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.png"
        filepath = os.path.join(screenshot_dir, filename)

        # 使用 get_screenshot 方法保存截图
        tab.get_screenshot(filepath)
        logging.info(f"已保存截图: {filepath}")
        return filepath
    except Exception as e:
        logging.error(f"截图保存失败: {str(e)}")
        return None


def handle_turnstile(tab, max_wait_time=60, retry_attempts=3):
    """
    处理 Turnstile 人机验证

    Args:
        tab: 浏览器标签页对象
        max_wait_time: 最大等待时间（秒）
        retry_attempts: 验证失败后的重试次数

    Returns:
        bool: 验证是否成功
    """
    logging.info("正在检测 Turnstile 验证...")
    start_time = time.time()

    success_selectors = {
        "password": "@name=password",
        "verification": "@data-index=0",
        "settings": "Account Settings",
    }

    while time.time() - start_time < max_wait_time:
        try:
            # 检查是否已经通过验证
            for name, selector in success_selectors.items():
                if tab.ele(selector, timeout=1):
                    logging.info(f"验证成功 - 已到达{name}页面")
                    break

            # 检查并处理 Turnstile 验证
            turnstile = tab.ele("@id=cf-turnstile", timeout=1)
            if turnstile:
                for attempt in range(retry_attempts):
                    try:
                        challengeCheck = (
                            turnstile.child()
                            .shadow_root.ele("tag:iframe")
                            .ele("tag:body")
                            .sr("tag:input")
                        )

                        if challengeCheck:
                            logging.info(
                                f"检测到 Turnstile 验证，正在处理... (尝试 {attempt + 1}/{retry_attempts})"
                            )
                            time.sleep(random.uniform(1, 2))
                            challengeCheck.click()
                            time.sleep(2)

                            # 保存验证过程的截图
                            save_screenshot(tab, f"turnstile_attempt_{attempt + 1}")

                            # 检查验证失败提示
                            error_text = (
                                "Can't verify the user is human. Please try again."
                            )

                            # 检查验证失败的标志，使用更精确的选择器
                            error_selectors = [
                                "@data-accent-color=red",  # 红色提示div
                                f"//div[contains(@class, 'rt-Text') and contains(text(), '{error_text}')]",
                                # 包含特定类和文本的div
                                f"//div[@data-accent-color='red' and contains(text(), '{error_text}')]",  # 最精确的选择器
                            ]

                            is_failed = any(
                                tab.ele(selector, timeout=2)
                                for selector in error_selectors
                            )

                            if not is_failed:
                                logging.info("人机验证成功")
                                save_screenshot(tab, "turnstile_success")
                                return True

                            logging.warning(
                                f"验证失败，尝试重试 ({attempt + 1}/{retry_attempts})"
                            )
                            # 保存失败的截图
                            save_screenshot(tab, f"turnstile_fail_{attempt + 1}")

                    except Exception as e:
                        logging.debug(f"处理验证时发生异常: {str(e)}")
                        continue

            time.sleep(1)

        except Exception as e:
            logging.debug(f"验证过程发生异常: {str(e)}")
            time.sleep(1)

    logging.error(f"Turnstile 验证超时，已等待 {max_wait_time} 秒")
    return False


def get_cursor_session_token(tab, max_attempts=3, retry_interval=2):
    """
    获取Cursor会话token，带有重试机制
    :param tab: 浏览器标签页
    :param max_attempts: 最大尝试次数
    :param retry_interval: 重试间隔(秒)
    :return: session token 或 None
    """
    logging.info("开始获取cookie")
    attempts = 0

    while attempts < max_attempts:
        try:
            cookies = tab.cookies()
            for cookie in cookies:
                if cookie.get("name") == "WorkosCursorSessionToken":
                    return cookie["value"].split("%3A%3A")[1]

            attempts += 1
            if attempts < max_attempts:
                logging.warning(
                    f"第 {attempts} 次尝试未获取到CursorSessionToken，{retry_interval}秒后重试..."
                )
                time.sleep(retry_interval)
            else:
                logging.error(
                    f"已达到最大尝试次数({max_attempts})，获取CursorSessionToken失败"
                )

        except Exception as e:
            logging.error(f"获取cookie失败: {str(e)}")
            attempts += 1
            if attempts < max_attempts:
                logging.info(f"将在 {retry_interval} 秒后重试...")
                time.sleep(retry_interval)

    return None


def update_cursor_auth(email=None, access_token=None, refresh_token=None):
    """
    更新Cursor的认证信息的便捷函数
    """
    auth_manager = CursorAuthManager()
    return auth_manager.update_auth(email, access_token, refresh_token)


def sign_up_account(browser, tab):
    logging.info("=== 开始注册账号流程 ===")
    logging.info(f"正在访问注册页面: {sign_up_url}")
    tab.get(sign_up_url)

    try:
        if tab.ele("@name=first_name"):
            logging.info("正在填写个人信息...")
            tab.actions.click("@name=first_name").input(first_name)
            logging.info(f"已输入名字: {first_name}")
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@name=last_name").input(last_name)
            logging.info(f"已输入姓氏: {last_name}")
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@name=email").input(account)
            logging.info(f"已输入邮箱: {account}")
            time.sleep(random.uniform(1, 3))

            logging.info("提交个人信息...")
            tab.actions.click("@type=submit")

    except Exception as e:
        logging.error(f"注册页面访问失败: {str(e)}")
        return False

    handle_turnstile(tab)

    try:
        if tab.ele("@name=password"):
            logging.info("正在设置密码...")
            tab.ele("@name=password").input(password)
            time.sleep(random.uniform(1, 3))

            logging.info("提交密码...")
            tab.ele("@type=submit").click()
            logging.info("密码设置完成，等待系统响应...")

    except Exception as e:
        logging.error(f"密码设置失败: {str(e)}")
        return False

    if tab.ele("This email is not available."):
        logging.error("注册失败：邮箱已被使用")
        return False

    handle_turnstile(tab)

    while True:
        try:
            if tab.ele("Account Settings"):
                logging.info("注册成功 - 已进入账户设置页面")
                break
            if tab.ele("@data-index=0"):
                logging.info("正在获取邮箱验证码...")
                code = email_handler.get_verification_code()
                if not code:
                    logging.error("获取验证码失败")
                    return False

                logging.info(f"成功获取验证码: {code}")
                logging.info("正在输入验证码...")
                i = 0
                for digit in code:
                    tab.ele(f"@data-index={i}").input(digit)
                    time.sleep(random.uniform(0.1, 0.3))
                    i += 1
                logging.info("验证码输入完成")
                break
        except Exception as e:
            logging.error(f"验证码处理过程出错: {str(e)}")

    handle_turnstile(tab)
    wait_time = random.randint(3, 6)
    for i in range(wait_time):
        logging.info(f"等待系统处理中... 剩余 {wait_time - i} 秒")
        time.sleep(1)

    logging.info("正在获取账户信息...")
    tab.get(settings_url)
    try:
        usage_selector = (
            "css:div.col-span-2 > div > div > div > div > "
            "div:nth-child(1) > div.flex.items-center.justify-between.gap-2 > "
            "span.font-mono.text-sm\\/\\[0\\.875rem\\]"
        )
        usage_ele = tab.ele(usage_selector)
        if usage_ele:
            usage_info = usage_ele.text
            total_usage = usage_info.split("/")[-1].strip()
            logging.info(f"账户可用额度上限: {total_usage}")
    except Exception as e:
        logging.error(f"获取账户额度信息失败: {str(e)}")

    logging.info("\n=== 注册完成 ===")
    account_info = f"Cursor 账号信息:\n邮箱: {account}\n密码: {password}"
    logging.info(account_info)
    time.sleep(5)
    return True


class EmailGenerator:
    def __init__(
            self,
            password="".join(
                random.choices(
                    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*",
                    k=12,
                )
            ),
    ):
        configInstance = Config()
        # configInstance.print_config()
        self.domain = configInstance.get_domain()
        self.default_password = password
        self.default_first_name = self.generate_random_name()
        self.default_last_name = self.generate_random_name()

    @staticmethod
    def generate_random_name(length=6):
        """生成随机用户名"""
        first_letter = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        rest_letters = "".join(
            random.choices("abcdefghijklmnopqrstuvwxyz", k=length - 1)
        )
        return first_letter + rest_letters

    def generate_email(self, length=8):
        """生成随机邮箱地址"""
        random_str = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=length))
        timestamp = str(int(time.time()))[-6:]  # 使用时间戳后6位
        return f"{random_str}{timestamp}@{self.domain}"

    def get_account_info(self):
        """获取完整的账号信息"""
        return {
            "email": self.generate_email(),
            "password": self.default_password,
            "first_name": self.default_first_name,
            "last_name": self.default_last_name,
        }


def get_user_agent():
    """获取user_agent"""
    try:
        # 使用JavaScript获取user agent
        browser_manager = BrowserManager()
        browser = browser_manager.init_browser()
        user_agent = browser.latest_tab.run_js("return navigator.userAgent")
        browser_manager.quit()
        return user_agent
    except Exception as e:
        logging.error(f"获取user agent失败: {str(e)}")
        return None


class MachineIDResetter:
    def __init__(self):
        self.is_windows = os.name == 'nt'
        self.winreg = __import__('winreg') if self.is_windows else None

    def _change_mac_address(self):
        """修改 MAC 地址"""
        try:
            # 导入 mac_address_changer 模块
            import mac_address_changer
            
            # 调用 change_mac_address 函数
            return mac_address_changer.change_mac_address()
            
        except Exception as e:
            logging.error(f"修改 MAC 地址失败: {str(e)}")
            return False

    def reset_machine_ids(self):
        """重置机器标识"""
        if self.is_windows:
            return self._reset_windows_machine_guid()
        else:
            # 在 macOS 上同时修改 ioreg 和 MAC 地址
            ioreg_success = self._setup_fake_ioreg()
            mac_success = self._change_mac_address()
            
            if ioreg_success and mac_success:
                logging.info("机器标识和 MAC 地址都已成功重置")
                return True
            elif ioreg_success:
                logging.warning("机器标识已重置，但 MAC 地址修改失败")
                return True
            elif mac_success:
                logging.warning("MAC 地址已修改，但机器标识重置失败")
                return False
            else:
                logging.error("机器标识和 MAC 地址修改都失败了")
                return False

    def _restore_windows_machine_guid(self):
        """恢复Windows的原始MachineGuid"""
        try:
            backup_dir = os.path.join(os.path.expanduser("~"), "MachineGuid_Backups")
            if not os.path.exists(backup_dir):
                logging.error("未找到备份文件夹")
                return False

            # 获取所有备份文件
            backup_files = sorted([f for f in os.listdir(backup_dir) if f.startswith("MachineGuid_")])
            if not backup_files:
                logging.error("未找到备份文件")
                return False

            # 让用户选择要恢复的备份
            print("\n可用的备份文件：")
            for i, file in enumerate(backup_files, 1):
                print(f"{i}. {file}")

            choice = input("\n请选择要恢复的备份文件编号（默认为1）: ").strip()
            choice = int(choice) if choice.isdigit() else 1

            if choice < 1 or choice > len(backup_files):
                logging.error("无效的选择")
                return False

            backup_file = os.path.join(backup_dir, backup_files[choice - 1])
            with open(backup_file, 'r') as f:
                original_guid = f.read().strip()

            # 恢复MachineGuid
            key_path = r"SOFTWARE\Microsoft\Cryptography"
            with self.winreg.OpenKey(self.winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                                     self.winreg.KEY_SET_VALUE) as key:
                self.winreg.SetValueEx(key, "MachineGuid", 0, self.winreg.REG_SZ, original_guid)

            logging.info(f"已恢复原始 MachineGuid: {original_guid}")
            return True

        except Exception as e:
            logging.error(f"恢复 MachineGuid 失败: {str(e)}")
            return False

    def _remove_fake_ioreg(self):
        """移除假的ioreg命令"""
        try:
            real_user = os.environ.get('SUDO_USER') or os.environ.get('USER')
            real_home = os.path.expanduser(f'~{real_user}')

            # 移除假命令
            fake_commands_dir = os.path.join(real_home, "fake-commands")
            ioreg_script = os.path.join(fake_commands_dir, "ioreg")

            if os.path.exists(ioreg_script):
                os.remove(ioreg_script)
                logging.info("已移除假的 ioreg 命令")

            # 从配置文件中移除PATH配置
            shell_files = [
                os.path.join(real_home, '.zshrc'),
                os.path.join(real_home, '.bash_profile'),
                os.path.join(real_home, '.bashrc'),
                os.path.join(real_home, '.profile')
            ]

            path_line = f'export PATH="{fake_commands_dir}:$PATH"'
            for shell_file in shell_files:
                if os.path.exists(shell_file):
                    with open(shell_file, 'r') as f:
                        lines = f.readlines()

                    with open(shell_file, 'w') as f:
                        for line in lines:
                            if path_line not in line:
                                f.write(line)

            logging.info("已从shell配置中移除PATH设置")
            logging.info("请重新打开终端使更改生效")
            return True

        except Exception as e:
            logging.error(f"移除假ioreg命令失败: {str(e)}")
            return False

    def _generate_guid(self):
        """生成新的GUID"""
        return str(uuid.uuid4())

    def _reset_windows_machine_guid(self):
        """重置Windows的MachineGuid"""
        try:
            new_guid = self._generate_guid()
            key_path = r"SOFTWARE\Microsoft\Cryptography"

            # 备份原始MachineGuid
            backup_dir = os.path.join(os.path.expanduser("~"), "MachineGuid_Backups")
            os.makedirs(backup_dir, exist_ok=True)

            # 读取当前值并备份
            with self.winreg.OpenKey(self.winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                                     self.winreg.KEY_READ) as key:
                current_guid = self.winreg.QueryValueEx(key, "MachineGuid")[0]

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"MachineGuid_{timestamp}.txt")
            with open(backup_file, 'w') as f:
                f.write(current_guid)

            # 更新MachineGuid
            with self.winreg.OpenKey(self.winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                                     self.winreg.KEY_SET_VALUE) as key:
                self.winreg.SetValueEx(key, "MachineGuid", 0, self.winreg.REG_SZ, new_guid)

            logging.info(f"Windows MachineGuid已更新: {new_guid}")
            logging.info(f"原始MachineGuid已备份到: {backup_file}")
            return True
        except Exception as e:
            logging.error(f"更新Windows MachineGuid失败: {str(e)}")
            return False

    def _setup_fake_ioreg(self):
        """设置macOS的假ioreg命令"""
        try:
            real_user = os.environ.get('SUDO_USER') or os.environ.get('USER')
            real_home = os.path.expanduser(f'~{real_user}')

            # 创建假命令目录
            fake_commands_dir = os.path.join(real_home, "fake-commands")
            os.makedirs(fake_commands_dir, exist_ok=True)

            # 创建假的ioreg脚本
            ioreg_script = os.path.join(fake_commands_dir, "ioreg")
            with open(ioreg_script, 'w') as f:
                f.write('''#!/bin/bash
if [[ "$*" == *"-rd1 -c IOPlatformExpertDevice"* ]]; then
    # 获取真实的ioreg输出
    REAL_OUTPUT=$(/usr/sbin/ioreg -rd1 -c IOPlatformExpertDevice)
    
    # 检查是否包含 IOPlatformUUID
    if echo "$REAL_OUTPUT" | grep -q "IOPlatformUUID"; then
        # 生成新的UUID
        NEW_UUID=$(uuidgen)
        
        # 使用 perl 替换 UUID，保持原始格式
        echo "$REAL_OUTPUT" | perl -pe 's/"IOPlatformUUID" = "([^"]*)"/"IOPlatformUUID" = "'$NEW_UUID'"/'
    else
        # 如果没有找到 UUID，返回原始输出
        echo "$REAL_OUTPUT"
    fi
else
    # 其他命令直接传递给真实的ioreg
    /usr/sbin/ioreg "$@"
fi
''')

            # 设置执行权限
            os.chmod(ioreg_script, 0o755)

            # 修改环境变量
            shell_files = ['.zshrc', '.bash_profile', '.bashrc']
            path_line = f'export PATH="{fake_commands_dir}:$PATH"\n'
            
            for shell_file in shell_files:
                shell_path = os.path.join(real_home, shell_file)
                if os.path.exists(shell_path):
                    # 检查是否已经添加了路径
                    with open(shell_path, 'r') as f:
                        content = f.read()
                    if fake_commands_dir not in content:
                        with open(shell_path, 'a') as f:
                            f.write('\n# Added by Cursor Tool\n')
                            f.write(path_line)

            # 立即更新当前会话的 PATH
            os.environ['PATH'] = f"{fake_commands_dir}:{os.environ.get('PATH', '')}"

            logging.info(f"已创建假的 ioreg 命令: {ioreg_script}")
            logging.info("请重新打开终端或运行 source ~/.zshrc (或 .bash_profile) 使更改生效")
            
            # 测试 ioreg 命令是否工作
            try:
                # 获取原始输出用于比较
                original_output = subprocess.check_output(
                    ['/usr/sbin/ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'], 
                    text=True, 
                    stderr=subprocess.PIPE
                )
                
                # 获取假命令的输出
                test_output = subprocess.check_output(
                    [ioreg_script, '-rd1', '-c', 'IOPlatformExpertDevice'], 
                    text=True, 
                    stderr=subprocess.PIPE
                )
                
                if 'IOPlatformUUID' in test_output:
                    # 检查UUID是否确实被修改
                    original_uuid = original_output.split('IOPlatformUUID')[1].split('"')[2]
                    new_uuid = test_output.split('IOPlatformUUID')[1].split('"')[2]
                    
                    if original_uuid != new_uuid:
                        logging.info("ioreg 命令测试成功，UUID 已被成功修改")
                        logging.info(f"原始 UUID: {original_uuid}")
                        logging.info(f"新 UUID: {new_uuid}")
                    else:
                        logging.warning("ioreg 命令可能未正确工作：UUID 未被修改")
                else:
                    logging.warning("ioreg 命令可能未正确工作：未找到 UUID")
            except Exception as e:
                logging.error(f"测试 ioreg 命令失败: {e}")

            return True
        except Exception as e:
            logging.error(f"设置假 ioreg 命令失败: {str(e)}")
            return False


def show_menu():
    """显示功能选择菜单"""
    print("\n=== Cursor 工具 ===")
    print("\n=== 此工具免费，如果你是通过购买获得请立即退款并举报卖家 ===\n")
    print("1. 恢复原始机器标识")
    print("2. 重置 Cursor")
    print("3. 修改 Cursor 文件(仅限Cursor 0.45.x版本)")
    print("4. 恢复 Cursor 文件(仅限Cursor 0.45.x版本)")

    while True:
        choice = input("\n请选择功能 (1-4): ").strip()
        if choice in ['1', '2', '3', '4']:
            return int(choice)
        print("无效的选择，请重试")


def restart_cursor():
    if cursor_path:
        print("现在可以重新启动 Cursor 了。")

        # 询问是否自动启动 Cursor
        restart = input("\n是否要重新启动 Cursor？(y/n): ").strip().lower()
        if restart == 'y':
            inner_restart_cursor()


def inner_restart_cursor():
    try:
        logging.info(f"正在重新启动 Cursor: {cursor_path}")
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen([cursor_path], startupinfo=startupinfo, close_fds=True)
        else:
            subprocess.Popen(['open', cursor_path])
        logging.info("Cursor 已重新启动")
    except Exception as exception:
        logging.error(f"重启 Cursor 失败: {str(exception)}")


if __name__ == "__main__":
    if not is_admin():
        request_admin()

    print_logo()

    choice = show_menu()
    cursor_path = ""

    if choice == 1:
        # 恢复原始机器标识
        resetter = MachineIDResetter()
        if resetter.reset_machine_ids():
            print("\n机器标识已恢复")
        else:
            print("\n恢复失败")

        print("\n按回车键退出...", end='', flush=True)
        input()
        sys.exit(0)
    elif choice == 3:
        # 修改 Cursor 文件
        try:
            # 提示用户确认
            print("\n警告：接下来的操作将会修改 Cursor 的程序文件(会自动备份该文件)")
            confirm = input("\n是否继续？(y/n): ").strip().lower()
            if confirm != 'y':
                print("\n操作已取消")
                print("\n按回车键退出...", end='', flush=True)
                input()
                sys.exit(0)

            # 检查并等待 Cursor 退出
            success, cursor_path = ExitCursor()
            if not success:
                print("\n请先关闭 Cursor 程序后再继续")
                print("\n按回车键退出...", end='', flush=True)
                input()
                sys.exit(1)

            print("\n正在修改 Cursor 文件...")
            import patch_cursor_get_machine_id

            patch_cursor_get_machine_id.main()

            print("\n修改完成！")
            restart_cursor()
            print("\n按回车键退出...", end='', flush=True)
            input()
            sys.exit(0)
        except Exception as e:
            logging.error(f"修改 Cursor 文件失败: {str(e)}")
            print("\n修改失败，按回车键退出...", end='', flush=True)
            input()
            sys.exit(1)
    elif choice == 4:
        # 恢复 Cursor 文件备份
        try:
            # 检查并等待 Cursor 退出
            success, cursor_path = ExitCursor()
            if not success:
                print("\n请先关闭 Cursor 程序后再继续")
                print("\n按回车键退出...", end='', flush=True)
                input()
                sys.exit(1)

            print("\n正在恢复 Cursor 文件备份...")
            import patch_cursor_get_machine_id

            patch_cursor_get_machine_id.main(restore_mode=True)

            print("\n恢复完成！")

            restart_cursor()

            print("\n按回车键退出...", end='', flush=True)
            input()
            sys.exit(0)
        except Exception as e:
            logging.error(f"恢复 Cursor 文件备份失败: {str(e)}")
            print("\n恢复失败，按回车键退出...", end='', flush=True)
            input()
            sys.exit(1)

    # 原有的重置逻辑
    browser_manager = None
    try:
        logging.info("\n=== 初始化程序 ===")
        success, cursor_path = ExitCursor()
        logging.info("正在初始化浏览器...")

        # 获取user_agent
        user_agent = get_user_agent()
        if not user_agent:
            logging.error("获取user agent失败，使用默认值")
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        # 剔除user_agent中的"HeadlessChrome"
        user_agent = user_agent.replace("HeadlessChrome", "Chrome")

        browser_manager = BrowserManager()
        browser = browser_manager.init_browser(user_agent)

        # 获取并打印浏览器的user-agent
        user_agent = browser.latest_tab.run_js("return navigator.userAgent")

        logging.info("正在初始化邮箱验证模块...")
        email_handler = EmailVerificationHandler()

        logging.info("\n=== 配置信息 ===")
        login_url = "https://authenticator.cursor.sh"
        sign_up_url = "https://authenticator.cursor.sh/sign-up"
        settings_url = "https://www.cursor.com/settings"
        mail_url = "https://tempmail.plus"

        logging.info("正在生成随机账号信息...")
        email_generator = EmailGenerator()
        account = email_generator.generate_email()
        password = email_generator.default_password
        first_name = email_generator.default_first_name
        last_name = email_generator.default_last_name

        logging.info(f"生成的邮箱账号: {account}")
        auto_update_cursor_auth = True

        tab = browser.latest_tab

        tab.run_js("try { turnstile.reset() } catch(e) { }")

        logging.info("\n=== 开始注册流程 ===")
        logging.info(f"正在访问登录页面: {login_url}")
        tab.get(login_url)

        if sign_up_account(browser, tab):
            logging.info("正在获取会话令牌...")
            token = get_cursor_session_token(tab)
            if token:
                logging.info("更新认证信息...")
                update_cursor_auth(
                    email=account, access_token=token, refresh_token=token
                )

                logging.info("重置机器码...")
                MachineIDResetter().reset_machine_ids()

                logging.info("所有操作已完成")
            else:
                logging.error("获取会话令牌失败，注册流程未完成")

    except Exception as e:
        logging.error(f"程序执行出现错误: {str(e)}")
        import traceback

        logging.error(traceback.format_exc())
    finally:
        # 清理资源
        if browser_manager:
            browser_manager.quit()
            browser_manager = None

        print("\n程序执行完毕，按回车键退出...", end='', flush=True)
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            pass

        # 重启Cursor并退出
        restart_cursor()

        # 使用 sys.exit() 替代 os._exit()
        sys.exit(0)
