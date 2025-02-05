import ctypes
import os
import subprocess
import sys

from exit_cursor import ExitCursor
from reset_machine import MachineIDResetter

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


def show_menu():
    """显示功能选择菜单"""
    print("\n=== Cursor 工具 ===")
    print("=== 此工具免费，如果你是通过购买获得请立即退款并举报卖家 ===\n")
    print("1. 一键注册并且享用Cursor")
    print("2. 仅仅修改文件或设备信息")
    print("2. 恢复原始文件或设备信息")

    while True:
        choice = input("\n请选择功能 (1-3): ").strip()
        if choice in ['1', '2', '3']:
            return int(choice)
        print("无效的选择，请重试")


def restart_cursor():
    if cursor_path:
        print("现在可以重新启动 Cursor 了。")

        # 询问是否自动启动 Cursor
        restart = input("\n是否要重新启动 Cursor？(y/n): ").strip().lower()
        if restart == 'y':
            inner_restart_cursor()
    else:
        print("\n按回车键退出...", end='', flush=True)
        input()
        sys.exit(0)


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
        os._exit(0)
    except Exception as exception:
        logging.error(f"重启 Cursor 失败: {str(exception)}")
        os._exit(1)


if __name__ == "__main__":
    if not is_admin():
        request_admin()

    print_logo()

    choice = show_menu()
    cursor_path = ""

    if choice == 3:
        success, _ = ExitCursor()
        if success:
            MachineIDResetter().restore_machine_ids()
            print("\n文件或设备信息恢复成功，按回车键退出...", end='', flush=True)
            input()
            sys.exit(0)
        else:
            print("Cursor 未能自动关闭，请手动关闭后重试")    

    elif choice == 2:
        success, _ = ExitCursor()
        if success:
            MachineIDResetter().reset_machine_ids()
            print("\n文件或设备信息修改成功，按回车键退出...", end='', flush=True)
            input()
            sys.exit(0)
        else:
            print("Cursor 未能自动关闭，请手动关闭后重试")    

    # 原有的重置逻辑
    browser_manager = None
    is_success = False
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
                logging.info("处理Cursor...")
                MachineIDResetter().reset_machine_ids()
                logging.info("所有操作已完成")
                is_success = True
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

        if is_success:
            # 重启Cursor并退出
            restart_cursor()
        else:
            print("\n程序执行失败，按回车键退出...", end='', flush=True)
            input()
            sys.exit(1)
