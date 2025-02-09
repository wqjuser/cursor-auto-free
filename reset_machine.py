import hashlib
import json
import os
import sys
import uuid

from colorama import Fore, Style, init

import patch_cursor_get_machine_id 

# 初始化colorama
init()

# 定义emoji和颜色常量
EMOJI = {
    "FILE": "📄",
    "BACKUP": "💾",
    "SUCCESS": "✅",
    "ERROR": "❌",
    "INFO": "ℹ️",
    "RESET": "🔄",
}


class MachineIDResetter:
    def __init__(self):
        # 判断操作系统
        if sys.platform == "win32":  # Windows
            appdata = os.getenv("APPDATA")
            if appdata is None:
                raise EnvironmentError("APPDATA 环境变量未设置")
            self.db_path = os.path.join(
                appdata, "Cursor", "User", "globalStorage", "storage.json"
            )
        elif sys.platform == "darwin":  # macOS
            self.db_path = os.path.abspath(
                os.path.expanduser(
                    "~/Library/Application Support/Cursor/User/globalStorage/storage.json"
                )
            )
        elif sys.platform == "linux":  # Linux 和其他类Unix系统
            self.db_path = os.path.abspath(
                os.path.expanduser("~/.config/Cursor/User/globalStorage/storage.json")
            )
        else:
            raise NotImplementedError(f"不支持的操作系统: {sys.platform}")

    def generate_new_ids(self):
        """生成新的机器ID"""
        # 生成新的UUID
        dev_device_id = str(uuid.uuid4())

        # 生成新的machineId (64个字符的十六进制)
        machine_id = hashlib.sha256(os.urandom(32)).hexdigest()

        # 生成新的macMachineId (128个字符的十六进制)
        mac_machine_id = hashlib.sha512(os.urandom(64)).hexdigest()

        # 生成新的sqmId
        sqm_id = "{" + str(uuid.uuid4()).upper() + "}"

        return {
            "telemetry.devDeviceId": dev_device_id,
            "telemetry.macMachineId": mac_machine_id,
            "telemetry.machineId": machine_id,
            "telemetry.sqmId": sqm_id,
        }

    def reset_machine_ids(self):
        """重置机器ID并备份原文件"""
        try:
            pkg_path, _ = patch_cursor_get_machine_id.get_cursor_paths()
            # 获取版本号
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    version = json.load(f)["version"]
                    print(f"{Fore.CYAN}{EMOJI['INFO']}当前 Cursor 版本: {version}{Style.RESET_ALL}")
            except Exception as e:
                sys.exit(1)
            
            is_045_version = patch_cursor_get_machine_id.version_check(version, min_version="0.45.0")
            print(f"{Fore.CYAN}{EMOJI['INFO']}正在检查配置文件...{Style.RESET_ALL}")

            # 检查文件是否存在
            if not os.path.exists(self.db_path):
                print(
                    f"{Fore.RED}{EMOJI['ERROR']}配置文件不存在: {self.db_path}{Style.RESET_ALL}"
                )
                return False

            # 检查文件权限
            if not os.access(self.db_path, os.R_OK | os.W_OK):
                print(
                    f"{Fore.RED}{EMOJI['ERROR']} 无法读写配置文件，请检查文件权限！{Style.RESET_ALL}"
                )
                print(
                    f"{Fore.RED}{EMOJI['ERROR']} 如果你使用过 go-cursor-help 来修改 ID; 请修改文件只读权限 {self.db_path} {Style.RESET_ALL}"
                )
                return False

            # 读取现有配置
            print(f"{Fore.CYAN}{EMOJI['FILE']} 读取当前配置...{Style.RESET_ALL}")
            with open(self.db_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 只在备份文件不存在时创建备份
            backup_path = f"{self.db_path}.backup"
            if not os.path.exists(backup_path):
                print(f"{Fore.CYAN}{EMOJI['BACKUP']} 创建配置文件备份...{Style.RESET_ALL}")
                with open(backup_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4)
                print(f"{Fore.GREEN}{EMOJI['SUCCESS']} 备份文件已保存至: {backup_path}{Style.RESET_ALL}")
            else:
                print(f"{Fore.CYAN}{EMOJI['INFO']} 已存在备份文件，跳过备份步骤{Style.RESET_ALL}")

            # 生成新的ID
            print(f"{Fore.CYAN}{EMOJI['RESET']} 生成新的机器标识...{Style.RESET_ALL}")
            new_ids = self.generate_new_ids()

            # 更新配置
            config.update(new_ids)

            # 保存新配置
            print(f"{Fore.CYAN}{EMOJI['FILE']} 保存新配置...{Style.RESET_ALL}")
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)

            print(f"{Fore.GREEN}{EMOJI['SUCCESS']} 机器标识重置成功！{Style.RESET_ALL}")
            print(f"\n{Fore.CYAN}新的机器标识:{Style.RESET_ALL}")
            for key, value in new_ids.items():
                print(f"{EMOJI['INFO']} {key}: {Fore.GREEN}{value}{Style.RESET_ALL}")

            if  is_045_version:
                patch_cursor_get_machine_id.main(restore_mode=False)
            return True

        except PermissionError as e:
            print(f"{Fore.RED}{EMOJI['ERROR']} 权限错误: {str(e)}{Style.RESET_ALL}")
            print(
                f"{Fore.YELLOW}{EMOJI['INFO']} 请尝试以管理员身份运行此程序{Style.RESET_ALL}"
            )
            return False
        except Exception as e:
            print(f"{Fore.RED}{EMOJI['ERROR']} 重置过程出错: {str(e)}{Style.RESET_ALL}")

            return False

    def restore_machine_ids(self):
        """从备份文件恢复机器ID"""
        try:
            pkg_path, _ = patch_cursor_get_machine_id.get_cursor_paths()
            # 获取版本号
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    version = json.load(f)["version"]
                    print(f"{Fore.CYAN}{EMOJI['INFO']}当前 Cursor 版本: {version}{Style.RESET_ALL}")
            except Exception as e:
                sys.exit(1)
            
            is_045_version = patch_cursor_get_machine_id.version_check(version, min_version="0.45.0")
            backup_path = f"{self.db_path}.backup"

            # 检查备份文件是否存在
            if not os.path.exists(backup_path):
                print(f"{Fore.RED}{EMOJI['ERROR']} 备份文件不存在: {backup_path}{Style.RESET_ALL}")
                return False

            # 检查备份文件权限
            if not os.access(backup_path, os.R_OK):
                print(f"{Fore.RED}{EMOJI['ERROR']} 无法读取备份文件，请检查文件权限！{Style.RESET_ALL}")
                return False

            # 读取备份配置
            print(f"{Fore.CYAN}{EMOJI['FILE']} 读取备份配置...{Style.RESET_ALL}")
            with open(backup_path, "r", encoding="utf-8") as f:
                backup_config = json.load(f)

            # 检查原始文件权限
            if not os.access(self.db_path, os.W_OK):
                print(f"{Fore.RED}{EMOJI['ERROR']} 无法写入配置文件，请检查文件权限！{Style.RESET_ALL}")
                return False

            # 恢复配置
            print(f"{Fore.CYAN}{EMOJI['RESET']} 正在恢复配置...{Style.RESET_ALL}")
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(backup_config, f, indent=4)

            print(f"{Fore.GREEN}{EMOJI['SUCCESS']} 机器标识已恢复！{Style.RESET_ALL}")
            print(f"\n{Fore.CYAN}已恢复的机器标识:{Style.RESET_ALL}")
            for key in ['telemetry.devDeviceId', 'telemetry.macMachineId',
                        'telemetry.machineId', 'telemetry.sqmId']:
                if key in backup_config:
                    print(f"{EMOJI['INFO']} {key}: {Fore.GREEN}{backup_config[key]}{Style.RESET_ALL}")

            if  is_045_version:
                patch_cursor_get_machine_id.main(restore_mode=True)
                
            return True
            
        except json.JSONDecodeError:
            print(f"{Fore.RED}{EMOJI['ERROR']} 备份文件格式错误{Style.RESET_ALL}")
            return False
        except Exception as e:
            print(f"{Fore.RED}{EMOJI['ERROR']} 恢复过程出错: {str(e)}{Style.RESET_ALL}")
            return False


if __name__ == "__main__":
    print(f"\n{Fore.CYAN}{'=' * 50}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{EMOJI['RESET']} Cursor 机器标识重置工具{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 50}{Style.RESET_ALL}")

    resetter = MachineIDResetter()
    
    # 添加命令行参数支持
    if len(sys.argv) > 1 and sys.argv[1] == '--restore':
        resetter.restore_machine_ids()
    else:
        resetter.reset_machine_ids()

    print(f"\n{Fore.CYAN}{'=' * 50}{Style.RESET_ALL}")
    input(f"{EMOJI['INFO']} 按回车键退出...")
