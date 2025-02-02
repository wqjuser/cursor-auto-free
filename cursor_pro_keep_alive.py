import os
import subprocess
import sys
import getpass
import ctypes

from exit_cursor import ExitCursor

# 禁用不必要的日志输出
os.environ["PYTHONVERBOSE"] = "0"
os.environ["PYINSTALLER_VERBOSE"] = "0"
os.environ["PYTHONWARNINGS"] = "ignore"

import time
import random
from cursor_auth_manager import CursorAuthManager
import os
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
    except:
        return False


def request_admin():
    script_path = os.path.abspath(__file__)
    
    if os.name == 'nt':  # Windows
        if not is_admin():
            try:
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, script_path, None, 1
                )
                sys.exit(0)
            except Exception as e:
                print(f"请求管理员权限失败: {e}")
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
        configInstance.print_config()
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
        if self.is_windows:
            import winreg
            self.winreg = winreg
    
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
    UUID=$(uuidgen)
    cat << INNEREOF
+-o Root  <class IORegistryEntry, id 0x100000100, retain 12>
  +-o IOPlatformExpertDevice  <class IOPlatformExpertDevice, id 0x100000110, registered, matched, active, busy 0 (0 ms), retain 35>
    | {
    |   "IOPlatformUUID" = "$UUID"
    | }
INNEREOF
else
    exec /usr/sbin/ioreg "$@"
fi
''')
            
            # 设置执行权限
            os.chmod(ioreg_script, 0o755)
            
            # 配置PATH
            shell_config_file = None
            shell = os.environ.get('SHELL', '').split('/')[-1]
            
            if shell == 'zsh':
                shell_config_file = os.path.join(real_home, '.zshrc')
            elif shell == 'bash':
                shell_config_file = os.path.join(real_home, '.bash_profile')
                if not os.path.exists(shell_config_file):
                    shell_config_file = os.path.join(real_home, '.bashrc')
            else:
                shell_config_file = os.path.join(real_home, '.profile')
            
            path_export = f'\nexport PATH="{fake_commands_dir}:$PATH"\n'
            
            # 检查配置是否已存在
            if os.path.exists(shell_config_file):
                with open(shell_config_file, 'r') as f:
                    if fake_commands_dir not in f.read():
                        with open(shell_config_file, 'a') as f:
                            f.write(path_export)
            
            logging.info(f"已创建假的ioreg命令: {ioreg_script}")
            logging.info(f"PATH配置已添加到: {shell_config_file}")
            return True
        except Exception as e:
            logging.error(f"设置假ioreg命令失败: {str(e)}")
            return False

    def reset_machine_ids(self):
        """重置机器标识"""
        if self.is_windows:
            return self._reset_windows_machine_guid()
        else:
            return self._setup_fake_ioreg()


def show_menu():
    """显示功能选择菜单"""
    print("\n=== Cursor 工具 ===")
    print("1. 恢复原始机器标识")
    print("2. 重置 Cursor")
    print("3. 修改 Cursor 文件(仅限Cursor 0.45.x版本)")
    print("4. 恢复 Cursor 文件(仅限Cursor 0.45.x版本)")
    
    while True:
        choice = input("\n请选择功能 (1-4): ").strip()
        if choice in ['1', '2', '3', '4']:
            return int(choice)
        print("无效的选择，请重试")


if __name__ == "__main__":
    if not is_admin():
        request_admin()
    
    print_logo()
    
    choice = show_menu()
    
    if choice == 1:
        # 恢复原始机器标识
        resetter = MachineIDResetter()
        if resetter.reset_machine_ids():
            print("\n机器标识已恢复")
        else:
            print("\n恢复失败")
        
        print("\n按回车键退出...", end='', flush=True)
        input()
        os._exit(0)
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
                os._exit(0)

            # 检查并等待 Cursor 退出
            success, cursor_path = ExitCursor()
            if not success:
                print("\n请先关闭 Cursor 程序后再继续")
                print("\n按回车键退出...", end='', flush=True)
                input()
                os._exit(1)

            print("\n正在修改 Cursor 文件...")
            import patch_cursor_get_machine_id
            patch_cursor_get_machine_id.main()
            
            print("\n修改完成！")
            print("现在可以重新启动 Cursor 了。")
            
            # 询问是否自动启动 Cursor
            restart = input("\n是否要重新启动 Cursor？(y/n): ").strip().lower()
            if restart == 'y':
                try:
                    logging.info(f"正在重新启动 Cursor: {cursor_path}")
                    if os.name == 'nt':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        subprocess.Popen([cursor_path], startupinfo=startupinfo, close_fds=True)
                    else:
                        subprocess.Popen(['open', cursor_path])
                    logging.info("Cursor 已重新启动")
                except Exception as e:
                    logging.error(f"重启 Cursor 失败: {str(e)}")
            
            print("\n按回车键退出...", end='', flush=True)
            input()
            os._exit(0)
        except Exception as e:
            logging.error(f"修改 Cursor 文件失败: {str(e)}")
            print("\n修改失败，按回车键退出...", end='', flush=True)
            input()
            os._exit(1)
    elif choice == 4:
        # 恢复 Cursor 文件备份
        try:
            # 检查并等待 Cursor 退出
            success, cursor_path = ExitCursor()
            if not success:
                print("\n请先关闭 Cursor 程序后再继续")
                print("\n按回车键退出...", end='', flush=True)
                input()
                os._exit(1)

            print("\n正在恢复 Cursor 文件备份...")
            import patch_cursor_get_machine_id
            patch_cursor_get_machine_id.main(restore_mode=True)
            
            print("\n恢复完成！")
            print("现在可以重新启动 Cursor 了。")
            
            # 询问是否自动启动 Cursor
            restart = input("\n是否要重新启动 Cursor？(y/n): ").strip().lower()
            if restart == 'y':
                try:
                    logging.info(f"正在重新启动 Cursor: {cursor_path}")
                    if os.name == 'nt':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        subprocess.Popen([cursor_path], startupinfo=startupinfo, close_fds=True)
                    else:
                        subprocess.Popen(['open', cursor_path])
                    logging.info("Cursor 已重新启动")
                except Exception as e:
                    logging.error(f"重启 Cursor 失败: {str(e)}")
            
            print("\n按回车键退出...", end='', flush=True)
            input()
            os._exit(0)
        except Exception as e:
            logging.error(f"恢复 Cursor 文件备份失败: {str(e)}")
            print("\n恢复失败，按回车键退出...", end='', flush=True)
            input()
            os._exit(1)
    
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
        if cursor_path:
            try:
                logging.info(f"正在重新启动 Cursor: {cursor_path}")
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    subprocess.Popen([cursor_path], startupinfo=startupinfo, close_fds=True)
                else:
                    subprocess.Popen(['open', cursor_path])
                logging.info("Cursor 已重新启动")
            except Exception as e:
                logging.error(f"重启 Cursor 失败: {str(e)}")

        # 强制退出程序
        os._exit(0)
