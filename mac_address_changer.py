#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import random
import time
import logging
import os
import sys
from spoofmac.interface import set_interface_mac, get_interface_mac

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
        def generate_mac():
            prefixes = [
                'a4:83:e7',  # Apple, Inc.
                'a4:5e:60',  # Apple, Inc.
                'ac:bc:32',  # Apple, Inc.
                'b8:e8:56',  # Apple, Inc.
            ]
            prefix = random.choice(prefixes)
            suffix = ':'.join([f'{random.randint(0, 255):02x}' for _ in range(3)])
            return f"{prefix}:{suffix}"

        new_mac = generate_mac()
        logger.info(f"正在修改 MAC 地址: {new_mac}")

        try:
            # 获取当前 MAC 地址
            original_mac = get_interface_mac(wifi_device)
            logger.info(f"当前 MAC 地址: {original_mac}")

            # 关闭 Wi-Fi
            subprocess.run(['networksetup', '-setairportpower', wifi_device, 'off'], 
                         check=True)
            
            # 等待接口完全关闭
            time.sleep(2)
            
            # 修改 MAC 地址
            set_interface_mac(wifi_device, new_mac)
            
            time.sleep(1)
            
            # 重新开启 Wi-Fi
            subprocess.run(['networksetup', '-setairportpower', wifi_device, 'on'], 
                         check=True)
            
            # 等待接口完全启动
            time.sleep(3)

            # 验证修改
            current_mac = get_interface_mac(wifi_device)
            
            if current_mac.lower() == new_mac.lower():
                logger.info(f"MAC 地址已成功修改为: {new_mac}")
                return True
            else:
                logger.error(f"MAC 地址修改验证失败: 当前={current_mac}, 预期={new_mac}")
                return False

        except Exception as e:
            logger.error(f"修改 MAC 地址时发生错误: {str(e)}")
            # 确保 Wi-Fi 重新开启
            try:
                subprocess.run(['networksetup', '-setairportpower', wifi_device, 'on'], 
                             check=True)
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