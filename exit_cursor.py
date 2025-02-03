import psutil
from logger import logging  
import time

def ExitCursor(timeout=8):
    """
    温和地关闭 Cursor 进程并返回进程文件路径
    
    Args:
        timeout (int): 等待进程自然终止的超时时间（秒）
    Returns:
        tuple: (bool, str) - (是否成功关闭所有进程, Cursor可执行文件路径)
    """
    try:
        logging.info("开始退出Cursor...")
        cursor_processes = []
        cursor_path = ""
        
        # 收集所有 Cursor 进程
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'].lower() in ['cursor.exe', 'cursor']:
                    try:
                        # 只需要记录第一个找到的路径
                        if not cursor_path:
                            raw_path = proc.exe()
                            # 路径处理:
                            # - Mac: 截取到.app结尾 (如/Applications/Cursor.app)
                            # - Linux: 保持原路径 (如/usr/bin/cursor或/opt/cursor/cursor)
                            # - Windows: 保持原路径 (如C:\Users\Username\AppData\Local\Programs\Cursor\Cursor.exe)
                            if raw_path and '.app' in raw_path:  # Mac系统
                                cursor_path = raw_path[:raw_path.find('.app') + 4]
                            else:  # Linux/Windows系统
                                cursor_path = raw_path
                            logging.info(f"Cursor 进程位于: {cursor_path}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        logging.warning(f"无法获取进程 (PID: {proc.pid}) 的文件路径")
                    cursor_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not cursor_processes:
            logging.info("未发现运行中的 Cursor 进程")
            return True, cursor_path

        # 温和地请求进程终止
        for proc in cursor_processes:
            try:
                if proc.is_running():
                    proc.terminate()# 发送终止信号
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 等待进程自然终止
        start_time = time.time()
        while time.time() - start_time < timeout:
            still_running = []
            for proc in cursor_processes:
                try:
                    if proc.is_running():
                        still_running.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not still_running:
                logging.info("所有 Cursor 进程已正常关闭")
                return True, cursor_path
                
            time.sleep(3)
            
        # 如果超时后仍有进程在运行
        if still_running:
            process_list = ", ".join([str(p.pid) for p in still_running])
            logging.warning(f"以下进程未能在规定时间内关闭: {process_list}")
            return False, cursor_path
            
        return True, cursor_path

    except Exception as e:
        logging.error(f"关闭 Cursor 进程时发生错误: {str(e)}")
        return False, ""

if __name__ == "__main__":
    success, path = ExitCursor()
    if path:
        print(f"Cursor 程序路径: {path}")
