import os
import random
import sys

from dotenv import load_dotenv

from logger import logging


class Config:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # 如果已经初始化过，直接返回
        if self._initialized:
            return

        self._initialized = True

        # 获取应用程序的根目录路径
        if getattr(sys, "frozen", False):
            # 如果是打包后的可执行文件
            application_path = os.path.dirname(sys.executable)
        else:
            # 如果是开发环境
            application_path = os.path.dirname(os.path.abspath(__file__))

        # 指定 .env 文件的路径
        dotenv_path = os.path.join(application_path, ".env")
        domains = ["wqj666.ggff.net", "wqjsonder.ggff.net"]
        # 设置默认值
        self.imap = False
        self.temp_mail = "sonder"  # 默认设置为 wqj666
        self.domain = random.choice(domains)

        # 检查是否支持颜色输出
        def supports_color():
            if os.name == 'nt':
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    handle = kernel32.GetStdHandle(-11)
                    mode = ctypes.c_ulong()
                    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                        return False
                    mode.value |= 0x0004
                    if not kernel32.SetConsoleMode(handle, mode):
                        return False
                    return True
                except:
                    return False
            return True

        # 根据是否支持颜色选择输出格式
        if supports_color():
            yellow = "\033[33m"
            reset = "\033[0m"
        else:
            yellow = ""
            reset = ""

        # 如果.env文件存在，则读取配置
        if os.path.exists(dotenv_path):
            # 加载 .env 文件，设置 override=False 防止创建新文件
            load_dotenv(dotenv_path, override=False)

            self.domain = os.getenv("DOMAIN", self.domain).strip()
            env_temp_mail = os.getenv("TEMP_MAIL", "").strip()

            # 只有当环境变量中存在 TEMP_MAIL 时才覆盖默认值
            if env_temp_mail:
                self.temp_mail = env_temp_mail.split("@")[0]

            # 如果临时邮箱为null则加载IMAP
            if self.temp_mail == "null":
                self.imap = True
                self.imap_server = os.getenv("IMAP_SERVER", "").strip()
                self.imap_port = os.getenv("IMAP_PORT", "").strip()
                self.imap_user = os.getenv("IMAP_USER", "").strip()
                self.imap_pass = os.getenv("IMAP_PASS", "").strip()
                self.imap_dir = os.getenv("IMAP_DIR", "inbox").strip()
        else:
            self.print_config()

        self.check_config()

    def get_temp_mail(self):

        return self.temp_mail

    def get_imap(self):
        if not self.imap:
            return False
        return {
            "imap_server": self.imap_server,
            "imap_port": self.imap_port,
            "imap_user": self.imap_user,
            "imap_pass": self.imap_pass,
            "imap_dir": self.imap_dir,
        }

    def get_domain(self):
        return self.domain

    def check_config(self):
        """检查配置项是否有效

        检查规则：
        1. 如果使用 tempmail.plus，需要配置 TEMP_MAIL 和 DOMAIN
        2. 如果使用 IMAP，需要配置 IMAP_SERVER、IMAP_PORT、IMAP_USER、IMAP_PASS
        3. IMAP_DIR 是可选的
        """
        # 基础配置检查
        required_configs = {
            "domain": "域名",
        }

        # 检查基础配置
        for key, name in required_configs.items():
            if not self.check_is_valid(getattr(self, key)):
                raise ValueError(f"{name}未配置，请在 .env 文件中设置 {key.upper()}")

        # 检查邮箱配置
        if self.temp_mail != "null":
            # tempmail.plus 模式
            if not self.check_is_valid(self.temp_mail):
                raise ValueError("临时邮箱未配置，请在 .env 文件中设置 TEMP_MAIL")
        else:
            # IMAP 模式
            imap_configs = {
                "imap_server": "IMAP服务器",
                "imap_port": "IMAP端口",
                "imap_user": "IMAP用户名",
                "imap_pass": "IMAP密码",
            }

            for key, name in imap_configs.items():
                value = getattr(self, key)
                if value == "null" or not self.check_is_valid(value):
                    raise ValueError(
                        f"{name}未配置，请在 .env 文件中设置 {key.upper()}"
                    )

            # IMAP_DIR 是可选的，如果设置了就检查其有效性
            if self.imap_dir != "null" and not self.check_is_valid(self.imap_dir):
                raise ValueError(
                    "IMAP收件箱目录配置无效，请在 .env 文件中正确设置 IMAP_DIR"
                )

    def check_is_valid(self, value):
        """检查配置项是否有效

        Args:
            value: 配置项的值

        Returns:
            bool: 配置项是否有效
        """
        return isinstance(value, str) and len(str(value).strip()) > 0

    def print_config(self):
        # 检查是否支持颜色输出
        def supports_color():
            if os.name == 'nt':
                try:
                    # Windows 10 build 14931 或更高版本支持 ANSI
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    # 获取控制台输出句柄
                    handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
                    mode = ctypes.c_ulong()
                    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                        return False
                    # 启用 ANSI 转义序列
                    mode.value |= 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
                    if not kernel32.SetConsoleMode(handle, mode):
                        return False
                    return True
                except:
                    return False
            return True

        # 根据是否支持颜色选择输出格式
        if supports_color():
            green = "\033[32m"
            reset = "\033[0m"
            yellow = "\033[33m"
        else:
            green = ""
            reset = ""
            yellow = ""

        if not os.path.exists(".env"):
            logging.info(f"{yellow}未找到.env文件，使用默认配置{reset}")

        if self.imap:
            logging.info(f"{green}IMAP服务器: {self.imap_server}{reset}")
            logging.info(f"{green}IMAP端口: {self.imap_port}{reset}")
            logging.info(f"{green}IMAP用户名: {self.imap_user}{reset}")
            logging.info(f"{green}IMAP密码: {'*' * len(self.imap_pass)}{reset}")
            logging.info(f"{green}IMAP收件箱目录: {self.imap_dir}{reset}")
        # if self.temp_mail != "null":
        # 移除默认信息的打印
        # logging.info(f"{green}临时邮箱: {self.temp_mail}@{self.domain}{reset}")
        # logging.info(f"{green}域名: {self.domain}{reset}")


# 使用示例
if __name__ == "__main__":
    try:
        config = Config()
        print("环境变量加载成功！")
        # config.print_config()
    except ValueError as e:
        print(f"错误: {e}")
