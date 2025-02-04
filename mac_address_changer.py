#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import random
import time
import logging
import os
import sys
from spoofmac.interface import set_interface_mac

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
        # 先打印完整输出，看看具体格式
        logger.info(f"MAC 地址命令输出:\n{result}")
        
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

def set_mac_address(device, mac):
    """修改网络接口的 MAC 地址"""
    try:
        # 关闭网络接口
        subprocess.run(['sudo', 'ifconfig', device, 'down'], check=True)
        
        # 修改 MAC 地址
        subprocess.run(['sudo', 'ifconfig', device, 'lladdr', mac], check=True)
        
        # 重新启用网络接口
        subprocess.run(['sudo', 'ifconfig', device, 'up'], check=True)
        
        return True
    except Exception as e:
        logger.error(f"修改 MAC 地址失败: {str(e)}")
        return False

def change_mac_address():
    """修改 MAC 地址"""
    try:
        # 检查是否安装了 spoof-mac
        try:
            subprocess.run(['which', 'spoof-mac'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            logging.info("正在安装 spoof-mac...")
            try:
                # 使用 pip3 安装 spoof-mac
                subprocess.run(['pip3', 'install', 'SpoofMAC'], check=True)
                logging.info("spoof-mac 安装成功")
            except subprocess.CalledProcessError as e:
                logging.error(f"安装 spoof-mac 失败: {str(e)}")
                return False

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
            logging.error("未找到 Wi-Fi 接口")
            return False

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

        new_mac = generate_mac()
        logging.info(f"正在修改 MAC 地址: {new_mac}")

        try:
            # 关闭 Wi-Fi
            subprocess.run(['networksetup', '-setairportpower', wifi_device, 'off'],
                           check=True)

            # 等待接口完全关闭
            time.sleep(1)

            # 使用 spoof-mac 修改 MAC 地址
            subprocess.run([
                'sudo', 'spoof-mac', 'set', new_mac, wifi_device
            ], check=True)

            # 等待修改生效
            time.sleep(1)

            # 重新开启 Wi-Fi
            subprocess.run(['networksetup', '-setairportpower', wifi_device, 'on'],
                           check=True)

            # 等待接口完全启动
            time.sleep(2)

            # 验证修改
            result = subprocess.check_output(['ifconfig', wifi_device], text=True)
            if new_mac.lower() in result.lower():
                logging.info(f"MAC 地址已成功修改为: {new_mac}")
                return True
            else:
                logging.error("MAC 地址修改验证失败")
                return False

        except subprocess.CalledProcessError as e:
            logging.error(f"修改 MAC 地址时发生错误: {str(e)}")
            # 确保 Wi-Fi 重新开启
            try:
                subprocess.run(['networksetup', '-setairportpower', wifi_device, 'on'],
                               check=True)
            except:
                pass
            return False

    except Exception as e:
        logging.error(f"修改 MAC 地址失败: {str(e)}")
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