#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import random
import subprocess
import sys
import time


# 配置日志
def setup_logging():
    """配置并返回logger实例"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


logger = setup_logging()


def is_admin():
    """检查是否有管理员权限"""
    try:
        return os.geteuid() == 0
    except Exception:
        return False


def get_interface_mac(interface):
    """获取网络接口的 MAC 地址"""
    try:
        # 使用 networksetup -getmacaddress 命令获取 MAC 地址
        result = subprocess.check_output(
            ['networksetup', '-getmacaddress', interface],
            text=True
        )

        # 如果输出为空，直接返回 None
        if not result.strip():
            logger.error("命令输出为空")
            return None

        try:
            # 尝试解析 MAC 地址
            mac = result.split(': ')[1].split(' ')[0].strip()
            if not mac:
                logger.error("解析到的 MAC 地址为空")
                return None

            # 验证 MAC 地址格式
            if len(mac.split(':')) != 6:
                logger.error(f"MAC 地址格式不正确: {mac}")
                return None

            return mac.lower()
        except IndexError:
            logger.error(f"MAC 地址解析失败，输出格式不符合预期: {result}")
            return None

    except Exception as e:
        logger.error(f"获取 MAC 地址失败: {str(e)}")
        return None

# 生成随机 MAC 地址
def generate_mac():
    # 生成第一个字节，确保是偶数（本地管理的MAC地址）
    first_byte = random.randint(0, 255) & 0xfe  # 确保最后一位是0
    # 生成剩余的字节
    other_bytes = [random.randint(0, 255) for _ in range(5)]
    # 组合所有字节
    all_bytes = [first_byte] + other_bytes
    # 格式化为MAC地址格式
    return ':'.join([f'{b:02x}' for b in all_bytes])

def change_mac_address():
    """修改 MAC 地址"""
    try:
        # 获取网络接口列表
        interfaces = subprocess.check_output(['networksetup', '-listallhardwareports'],
                                             text=True).split('\n')

        # 找到 Wi-Fi 接口
        wifi_device = None
        for i, line in enumerate(interfaces):
            if 'Wi-Fi' in line or 'AirPort' in line:
                # 下一行包含设备名称
                device_line = interfaces[i + 1]
                wifi_device = device_line.split(': ')[1].strip()
                break

        if not wifi_device:
            logger.error("未找到 Wi-Fi 接口")
            return False

        # 生成随机 MAC 地址
        new_mac = generate_mac()
        logger.info(f"正在修改 MAC 地址: {new_mac}")

        try:
            # 获取当前 MAC 地址
            original_mac = get_interface_mac(wifi_device)
            logger.info(f"当前 MAC 地址: {original_mac}")

            # 关闭 网络接口
            subprocess.run(['sudo', 'ifconfig', wifi_device, 'down'], check=True)

            # 修改 MAC 地址
            subprocess.run(['sudo', 'ifconfig', wifi_device, 'ether', new_mac])

            time.sleep(1)

            # 重新开启 网络接口
            subprocess.run(['sudo', 'ifconfig', wifi_device, 'up'], check=True)

            # 等待接口完全启动
            time.sleep(1)
            return True

        except Exception as e:
            logger.error(f"修改 MAC 地址时发生错误: {str(e)}")
            # 确保 网络接口 重新开启
            try:
                subprocess.run(['sudo', 'ifconfig', wifi_device, 'up'], check=True)
            except:
                pass
            return False

    except Exception as e:
        logger.error(f"修改 MAC 地址失败: {str(e)}")
        return False


def main():
    """主函数"""
    if not is_admin():
        logger.error("需要管理员权限来运行此程序")
        print(f"\n请使用以下命令运行：\nsudo {sys.argv[0]}")
        sys.exit(1)

    if change_mac_address():
        logger.info("MAC 地址修改成功")
    else:
        logger.error("MAC 地址修改失败")


if __name__ == "__main__":
    main()
