import ctypes
import os
import subprocess
import sys
from enum import Enum
from typing import Optional

import requests  # 添加到文件顶部的导入部分

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

# 定义 EMOJI 字典
EMOJI = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️"}


class VerificationStatus(Enum):
    """验证状态枚举"""

    PASSWORD_PAGE = "@name=password"
    CAPTCHA_PAGE = "@data-index=0"
    ACCOUNT_SETTINGS = "Account Settings"


class TurnstileError(Exception):
    """Turnstile 验证相关异常"""

    pass


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


def save_screenshot(tab, stage: str, timestamp: bool = True) -> None:
    """
    保存页面截图

    Args:
        tab: 浏览器标签页对象
        stage: 截图阶段标识
        timestamp: 是否添加时间戳
    """
    try:
        # 创建 screenshots 目录
        screenshot_dir = "screenshots"
        if not os.path.exists(screenshot_dir):
            os.makedirs(screenshot_dir)

        # 生成文件名
        if timestamp:
            filename = f"turnstile_{stage}_{int(time.time())}.png"
        else:
            filename = f"turnstile_{stage}.png"

        filepath = os.path.join(screenshot_dir, filename)

        # 保存截图
        tab.get_screenshot(filepath)
        logging.debug(f"截图已保存: {filepath}")
    except Exception as e:
        logging.warning(f"截图保存失败: {str(e)}")


def check_verification_success(tab) -> Optional[VerificationStatus]:
    """
    检查验证是否成功
    Args:
        tab: 浏览器标签页
    Returns:
        VerificationStatus: 验证成功时返回对应状态，失败返回 None
    """
    # 检查是否到达成功页面
    for status in VerificationStatus:
        if tab.ele(status.value):
            logging.info(f"验证成功 - 已到达{status.name}页面")
            return status

    return None


def handle_turnstile(tab, max_retries: int = 2, retry_interval: tuple = (1, 2)) -> bool:
    """处理 Turnstile 验证"""
    logging.info("正在检测 Turnstile 验证...")
    save_screenshot(tab, "start")
    retry_count = 0
    try:
        while retry_count < max_retries:
            retry_count += 1
            logging.debug(f"第 {retry_count} 次尝试验证")

            try:
                # 定位验证框元素
                challenge_check = (
                    tab.ele("@id=cf-turnstile", timeout=2)
                    .child()
                    .shadow_root.ele("tag:iframe")
                    .ele("tag:body")
                    .sr("tag:input")
                )

                if challenge_check:
                    logging.info("检测到 Turnstile 验证框，开始处理...")
                    time.sleep(random.uniform(1, 3))
                    challenge_check.click()
                    time.sleep(2)
                    save_screenshot(tab, "clicked")

            except Exception as e:
                logging.debug(f"当前尝试未成功: {str(e)}")

            # 检查验证结果
            verification_result = check_verification_success(tab)
            if verification_result:
                return True
            elif retry_count < max_retries:
                time.sleep(random.uniform(*retry_interval))
                continue
            else:
                logging.error(f"验证失败 - 已达到最大重试次数 {max_retries}")
                save_screenshot(tab, "failed")
                return False

    except Exception as e:
        error_msg = f"Turnstile 验证过程发生异常: {str(e)}"
        logging.error(error_msg)
        save_screenshot(tab, "error")
        raise TurnstileError(error_msg)

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


def save_account_to_api(email, password, credits=150):
    """保存账号信息到API
    Args:
        email: 邮箱账号
        password: 密码
        credits: 额度，默认150
    Returns:
        bool: 是否保存成功
    """
    api_url = "https://accounts.zxai.fun/api/accounts"
    payload = {
        "accounts": [
            {
                "email": email,
                "password": password,
                "credits": credits
            }
        ]
    }

    try:
        response = requests.post(api_url, json=payload)
        if response.status_code == 200:
            logging.info("账号信息已成功保存到数据库")
            return True
        else:
            logging.error(f"保存账号信息失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"调用保存账号接口出错: {str(e)}")
        return False


def sign_up_account(browser, tab, is_auto_register=False):
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
    if not is_auto_register:
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
    if is_auto_register:
        # 调用接口保存账号
        try:
            credits = 150  # 默认额度
            save_result = save_account_to_api(account, password, credits)
            if save_result:
                logging.info("账号已成功保存到数据库")
            else:
                logging.warning("账号保存到数据库失败")
        except Exception as e:
            logging.error(f"保存账号过程出错: {str(e)}")

    time.sleep(5)
    return True


class EmailGenerator:
    def __init__(self):
        configInstance = Config()
        self.domain = configInstance.get_domain()
    
    @staticmethod
    def generate_password(length=12):
        """生成随机密码"""
        characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return "".join(random.choices(characters, k=length))

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
            "password": self.generate_password(),  # 每次调用都生成新的随机密码
            "first_name": self.generate_random_name(),
            "last_name": self.generate_random_name()
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


def sign_in_account(browser, tab, email, password=None):
    """登录Cursor账号"""
    logging.info("=== 开始登录账号流程 ===")
    login_url = "https://authenticator.cursor.sh"
    logging.info(f"正在访问登录页面: {login_url}")
    tab.get(login_url)

    try:
        # 输入邮箱
        if tab.ele("@name=email"):
            logging.info("正在输入邮箱...")
            tab.ele("@name=email").input(email)
            time.sleep(random.uniform(1, 3))
            tab.ele("@type=submit").click()
            logging.info("邮箱已提交")
    except Exception as e:
        logging.error(f"邮箱输入失败: {str(e)}")
        return False

    # 处理turnstile验证
    handle_turnstile(tab)
    try:
        # 检查是否存在密码输入框
        if tab.ele("@name=password"):
            if password:
                logging.info("使用密码登录...")
                tab.ele("@name=password").input(password)
                time.sleep(random.uniform(1, 2))
                tab.ele("@value=password").click()
            else:
                # 点击获取验证码按钮
                logging.info("点击发送验证码按钮...")
                magic_code_button = tab.ele("@value=magic-code")
                if magic_code_button:
                    magic_code_button.click()
                    logging.info("验证码发送按钮已点击")
                else:
                    logging.error("未找到发送验证码按钮")
                    return False

                # 提示用户输入验证码
                logging.info("\n请查看邮箱获取验证码")
                handle_turnstile(tab)
                verification_code = input("请输入验证码: ").strip()

                # 输入验证码
                logging.info("正在输入验证码...")
                i = 0
                for digit in verification_code:
                    tab.ele(f"@data-index={i}").input(digit)
                    time.sleep(random.uniform(0.1, 0.3))
                    i += 1
                logging.info("验证码输入完成")

    except Exception as e:
        logging.error(f"登录过程出错: {str(e)}")
        return False

    handle_turnstile(tab)

    # 检查是否登录成功
    try:
        if tab.ele("Account Settings", timeout=10):
            logging.info("登录成功!")
            return True
    except:
        logging.error("登录失败")
        return False

    return False


def show_menu():
    """显示功能选择菜单"""
    print("\n=== Cursor 工具 ===")
    print("=== 此工具免费，如果你是通过购买获得请立即退款并举报卖家 ===\n")
    print("1. 一键注册并且享用Cursor")
    print("2. 仅仅修改文件或设备信息")
    print("3. 恢复原始文件或设备信息")
    print("4. 重置设备并登录已有账号")
    print("5. 随机批量注册账号")

    while True:
        choice = input("\n请选择功能 (1-5): ").strip()
        if choice in ['1', '2', '3', '4', '5']:
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


def try_register(is_auto_register=False, pin=''):
    global browser_manager, email_handler, sign_up_url, settings_url, account, password, first_name, last_name, is_success
    logging.info("\n开始注册账号")

    logging.info("正在初始化浏览器...")
    # 获取user_agent
    user_agent = get_user_agent()
    if not user_agent:
        logging.error("获取user agent失败，使用默认值")
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    # 剔除user_agent中的"HeadlessChrome"
    user_agent = user_agent.replace("HeadlessChrome", "Chrome")
    browser_manager = BrowserManager()
    browser = browser_manager.init_browser(user_agent=user_agent)
    # 获取并打印浏览器的user-agent
    user_agent = browser.latest_tab.run_js("return navigator.userAgent")

    logging.info("正在初始化邮箱验证模块...")
    email_handler = EmailVerificationHandler(pin=pin)

    logging.info("\n=== 配置信息 ===")
    login_url = "https://authenticator.cursor.sh"
    sign_up_url = "https://authenticator.cursor.sh/sign-up"
    settings_url = "https://www.cursor.com/settings"
    logging.info("正在生成随机账号信息...")
    email_generator = EmailGenerator()
    account_info = email_generator.get_account_info()  # 获取包含随机密码的账号信息
    account = account_info["email"]
    password = account_info["password"]
    first_name = account_info["first_name"]
    last_name = account_info["last_name"]
    logging.info(f"生成的邮箱账号: {account}")
    tab = browser.latest_tab
    tab.run_js("try { turnstile.reset() } catch(e) { }")
    logging.info(f"正在访问登录页面: {login_url}")
    tab.get(login_url)
    if sign_up_account(browser, tab, is_auto_register):
        if not is_auto_register:
            logging.info("正在获取会话令牌...")
            token = get_cursor_session_token(tab)
            if token:
                logging.info("更新认证信息...")
                update_cursor_auth(
                    email=account, access_token=token, refresh_token=token
                )

                logging.info("所有操作已完成")
                is_success = True
            else:
                logging.error("获取会话令牌失败，注册流程未完成")
        else:
            is_success = True

    return browser_manager, is_success


def batch_register(num_accounts, pin=''):
    """批量注册账号
    Args:
        num_accounts: 要注册的账号数量
        pin: 邮箱 PIN 码
    """
    successful_accounts = []
    failed_attempts = 0

    for i in range(num_accounts):
        # 切换代理
        try:
            # 获取代理列表
            response = requests.get("http://127.0.0.1:9097/proxies/OKZTWO")
            if response.status_code == 200:
                proxy_data = response.json()
                all_proxies = proxy_data.get('all', [])

                # 筛选出以"专线"和"Lv"开头的代理
                valid_proxies = [
                    proxy for proxy in all_proxies
                    if proxy.startswith(('专线', 'Lv'))
                ]

                if valid_proxies:
                    # 随机选择代理并检查存活状态，直到找到可用的代理
                    random.shuffle(valid_proxies)  # 随机打乱代理列表
                    found_alive_proxy = False

                    for selected_proxy in valid_proxies:
                        # URL编码代理名称
                        encoded_proxy = requests.utils.quote(selected_proxy)

                        # 检查代理存活状态
                        check_response = requests.get(f"http://127.0.0.1:9097/proxies/{encoded_proxy}")
                        if check_response.status_code == 200:
                            proxy_info = check_response.json()
                            # 直接获取alive字段的值
                            is_alive = proxy_info.get('alive')
                            if is_alive:  # 如果代理存活
                                found_alive_proxy = True
                                logging.info(f"找到可用代理: {selected_proxy}")

                                # 切换到选中的代理
                                proxy_payload = {"name": selected_proxy}
                                put_response = requests.put(
                                    "http://127.0.0.1:9097/proxies/OKZTWO",
                                    json=proxy_payload
                                )

                                if put_response.status_code == 204:
                                    logging.info(f"成功切换到代理: {selected_proxy}")
                                    # 等待1秒
                                    time.sleep(1)

                                    # 获取当前IP
                                    try:
                                        ip_response = requests.get("http://ip-api.com/json")
                                        if ip_response.status_code == 200:
                                            ip_info = ip_response.json()
                                            current_ip = ip_info.get('query', 'unknown')
                                            logging.info(f"当前IP地址: {current_ip}")
                                    except Exception as e:
                                        logging.error(f"获取IP地址失败: {str(e)}")
                                    break
                                else:
                                    logging.error("切换代理失败")
                            else:
                                logging.warning(f"代理 {selected_proxy} 未存活 (alive: {is_alive})，尝试下一个")
                        else:
                            logging.error(f"检查代理 {selected_proxy} 状态失败")

                    if not found_alive_proxy:
                        logging.error("未找到可用的存活代理")
                        continue
                else:
                    logging.error("未找到符合条件的代理")
                    continue
            else:
                logging.error("获取代理列表失败")
                continue
        except Exception as e:
            logging.error(f"代理切换过程出错: {str(e)}")
            continue

        # 开始注册流程
        logging.info(f"\n=== 开始注册第 {i + 1}/{num_accounts} 个账号 ===")
        browser_manager = None
        try:
            browser_manager, is_success = try_register(is_auto_register=True, pin=pin)
            if is_success:
                successful_accounts.append({
                    'email': account,
                    'password': password
                })
                logging.info(f"第 {i + 1} 个账号注册成功")
            else:
                failed_attempts += 1
                logging.error(f"第 {i + 1} 个账号注册失败")
        except Exception as e:
            failed_attempts += 1
            logging.error(f"第 {i + 1} 个账号注册时发生错误: {str(e)}")
        finally:
            if browser_manager:
                browser_manager.quit()

        if i < num_accounts - 1:  # 如果不是最后一个账号，则添加延迟
            # 随机延迟10-20秒
            delay_seconds = random.uniform(10, 20)
            logging.info(f"为避免频繁注册，将等待 {delay_seconds:.1f} 秒后继续下一个注册...")
            time.sleep(delay_seconds)

    # 打印注册结果摘要
    logging.info("\n=== 批量注册完成 ===")
    logging.info(f"成功注册账号数: {len(successful_accounts)}")
    logging.info(f"失败注册数: {failed_attempts}")

    # 保存账号信息到文件
    if successful_accounts:
        filename = f"cursor_accounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=== Cursor 账号信息 ===\n\n")
                for acc in successful_accounts:
                    f.write(f"邮箱: {acc['email']}\n")
                    f.write(f"密码: {acc['password']}\n")
                    f.write("-" * 30 + "\n")
            logging.info(f"账号信息已保存到文件: {filename}")
        except Exception as e:
            logging.error(f"保存账号信息到文件时出错: {str(e)}")


if __name__ == "__main__":
    if not is_admin():
        request_admin()

    print_logo()

    choice = show_menu()  # 只获取选择
    cursor_path = ""

    if choice == 2:
        success, _ = ExitCursor()
        if success:
            MachineIDResetter().reset_machine_ids()
            print("\n文件或设备信息修改成功，按回车键退出...", end='', flush=True)
            input()
            sys.exit(0)
        else:
            print("Cursor 未能自动关闭，请手动关闭后重试")
    elif choice == 3:
        success, _ = ExitCursor()
        if success:
            MachineIDResetter().restore_machine_ids()
            print("\n文件或设备信息恢复成功，按回车键退出...", end='', flush=True)
            input()
            sys.exit(0)
        else:
            print("Cursor 未能自动关闭，请手动关闭后重试")
    elif choice == 5:
        logging.info('开始批量注册账号')
        time.sleep(1)
        while True:
            try:
                num = input("\n请输入要注册的账号数量: ").strip()
                num = int(num)
                if num > 0:
                    break
                print("请输入大于0的数字")
            except ValueError:
                print("请输入有效的数字")

        # 在这里获取 PIN 码
        pin = input("\n请输入邮箱 PIN 码: ").strip()
        logging.info("PIN 码已输入")

        batch_register(num, pin)
        print("\n批量注册完成，按回车键退出...", end='', flush=True)
        input()
        sys.exit(0)
    elif choice == 4:
        success, _ = ExitCursor()
        if success:
            logging.info('开始重置设备信息...')
            resetter = MachineIDResetter()
            try:
                # 执行重置并等待完成
                resetter.reset_machine_ids()
                logging.info('设备信息重置完成')
                
                # 添加一个短暂的延迟确保文件操作完全完成
                time.sleep(2)
                
                logging.info('开始登录账号')
                time.sleep(1)
                email = input("\n请输入邮箱: ").strip()
                login_type = input("选择登录方式(1:密码登录 2:验证码登录): ").strip()
                
                # 获取user_agent
                user_agent = get_user_agent()
                if not user_agent:
                    logging.error("获取user agent失败，使用默认值")
                    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                # 剔除user_agent中的"HeadlessChrome"
                user_agent = user_agent.replace("HeadlessChrome", "Chrome")

                browser_manager = BrowserManager()
                browser = browser_manager.init_browser(user_agent=user_agent)  # 使用有头模式
                tab = browser.latest_tab
                is_success = False
                try:
                    if login_type == "1":
                        password = input("请输入密码: ").strip()
                        is_success = sign_in_account(browser, tab, email, password)
                    else:
                        is_success = sign_in_account(browser, tab, email)

                    if is_success:
                        logging.info("正在获取会话令牌...")
                        token = get_cursor_session_token(tab)
                        if token:
                            logging.info("更新认证信息...")
                            update_cursor_auth(email=email, access_token=token, refresh_token=token)
                            logging.info("登录完成")
                        else:
                            logging.error("获取会话令牌失败")
                except Exception as e:
                    logging.error(f"登录过程出错: {str(e)}")
                finally:
                    if browser_manager:
                        browser_manager.quit()

                if is_success:
                    restart_cursor()
                else:
                    print("\n登录失败，按回车键退出...", end='', flush=True)
                    input()
                    sys.exit(0)
            except Exception as e:
                logging.error(f"重置设备信息时出错: {str(e)}")
                print("\n重置设备失败，按回车键退出...", end='', flush=True)
                input()
                sys.exit(1)
        else:
            print("Cursor 未能自动关闭，请手动关闭后重试")


    # 原有的重置逻辑
    browser_manager = None
    is_success = False
    try:
        logging.info("\n=== 初始化程序 ===")
        success, cursor_path = ExitCursor()

        logging.info("处理Cursor...")
        MachineIDResetter().reset_machine_ids()
        time.sleep(2)
        logging.info("\n是否需要注册账号？(y/n)")
        register = input().strip().lower()
        if register == "y":
            # 在这里获取 PIN 码
            pin = input("\n请输入邮箱 PIN 码: ").strip()
            logging.info("PIN 码已输入")
            browser_manager, _ = try_register(pin=pin)
        else:
            is_success = True

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
