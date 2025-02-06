import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import os
from cursor_pro_keep_alive import (
    is_admin, 
    request_admin,
    ExitCursor,
    MachineIDResetter,
    EmailVerificationHandler,
    BrowserManager,
    EmailGenerator,
    get_cursor_session_token,
    update_cursor_auth,
    sign_up_account,
    get_user_agent
)
from logo import print_logo
import time
import random
import logging
import tempfile
import datetime

# 配置日志
log_file = os.path.join(tempfile.gettempdir(), f'cursor_pro_ui_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# 在文件开头添加DPI感知支持
if os.name == 'nt':
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

class CursorProUI:
    def __init__(self):
        try:
            logging.info("Starting CursorPro UI")
            self.root = tk.Tk()
            
            # 在Mac上保持终端窗口打开
            if sys.platform == 'darwin':
                self.root.createcommand('exit', self.on_closing)
            
            # 添加窗口关闭处理
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            # 调整DPI缩放因子
            self.scale_factor = min(self.root.winfo_fpixels('1i') / 96, 1.5)
            
            self.root.title("Cursor Pro 工具")
            # 增加窗口基础高度，确保能显示完整日志框
            base_width = 600
            base_height = 600  # 从400增加到600
            scaled_width = int(base_width * self.scale_factor)
            scaled_height = int(base_height * self.scale_factor)
            self.root.geometry(f"{scaled_width}x{scaled_height}")
            
            # 设置主题色
            self.primary_color = "#2196F3"
            self.secondary_color = "#1976D2"
            self.bg_color = "#F5F5F5"
            
            self.root.configure(bg=self.bg_color)
            
            # 启用字体缩放
            self.setup_fonts()
            self.setup_ui()
            
        except Exception as e:
            logging.error(f"Initialization error: {str(e)}", exc_info=True)
            messagebox.showerror("错误", f"初始化失败: {str(e)}\n详细日志已保存到: {log_file}")
            sys.exit(1)
        
    def on_closing(self):
        """窗口关闭处理"""
        try:
            logging.info("Application closing")
            self.root.quit()
        except Exception as e:
            logging.error(f"Error during closing: {str(e)}", exc_info=True)
            sys.exit(1)
        
    def setup_fonts(self):
        """设置适应DPI的字体，调整基础字体大小"""
        self.title_font = ("Microsoft YaHei UI", int(18 * self.scale_factor), "bold")
        self.subtitle_font = ("Microsoft YaHei UI", int(9 * self.scale_factor))
        self.button_font = ("Microsoft YaHei UI", int(9 * self.scale_factor))
        self.text_font = ("Microsoft YaHei UI", int(9 * self.scale_factor))
    
    def setup_ui(self):
        # 标题框架
        title_frame = tk.Frame(self.root, bg=self.bg_color)
        title_frame.pack(pady=int(20 * self.scale_factor))
        
        title = tk.Label(
            title_frame,
            text="Cursor Pro 工具",
            font=self.title_font,
            fg=self.primary_color,
            bg=self.bg_color
        )
        title.pack()
        
        subtitle = tk.Label(
            title_frame,
            text="此工具免费，如果你是通过购买获得请立即退款并举报卖家",
            font=self.subtitle_font,
            fg="red",
            bg=self.bg_color
        )
        subtitle.pack(pady=int(5 * self.scale_factor))
        
        # 按钮框架
        button_frame = tk.Frame(self.root, bg=self.bg_color)
        button_frame.pack(pady=int(30 * self.scale_factor))
        
        # 自定义按钮样式
        style = ttk.Style()
        style.configure(
            "Custom.TButton",
            padding=int(10 * self.scale_factor),
            font=self.button_font
        )
        
        # 功能按钮
        btn1 = ttk.Button(
            button_frame,
            text="一键注册并且享用Cursor",
            style="Custom.TButton",
            command=self.handle_register
        )
        btn1.pack(pady=int(10 * self.scale_factor), 
                 padx=int(20 * self.scale_factor), 
                 fill=tk.X)
        
        btn2 = ttk.Button(
            button_frame,
            text="仅仅修改文件或设备信息",
            style="Custom.TButton",
            command=self.handle_reset
        )
        btn2.pack(pady=int(10 * self.scale_factor), 
                 padx=int(20 * self.scale_factor), 
                 fill=tk.X)
        
        btn3 = ttk.Button(
            button_frame,
            text="恢复原始文件或设备信息",
            style="Custom.TButton",
            command=self.handle_restore
        )
        btn3.pack(pady=int(10 * self.scale_factor), 
                 padx=int(20 * self.scale_factor), 
                 fill=tk.X)
        
        # 调整状态框架和文本框
        self.status_frame = tk.Frame(self.root, bg=self.bg_color)
        self.status_frame.pack(pady=int(20 * self.scale_factor), 
                             fill=tk.BOTH,  # 改为BOTH以便垂直和水平都能扩展
                             expand=True,   # 允许框架扩展填充剩余空间
                             padx=int(20 * self.scale_factor))
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(self.status_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.status_text = tk.Text(
            self.status_frame,
            height=12,  # 增加文本框的高度
            wrap=tk.WORD,
            font=self.text_font,
            bg="white",
            yscrollcommand=scrollbar.set  # 绑定滚动条
        )
        self.status_text.pack(fill=tk.BOTH, expand=True)  # 允许文本框扩展填充
        
        # 配置滚动条
        scrollbar.config(command=self.status_text.yview)
        
        # 设置文本框只读
        self.status_text.config(state='disabled')
        
    def update_status(self, message):
        """更新状态文本，确保线程安全"""
        def _update():
            self.status_text.config(state='normal')
            self.status_text.insert(tk.END, message + "\n")
            self.status_text.see(tk.END)
            self.status_text.config(state='disabled')
            
        # 如果在其他线程中调用，使用after方法确保在主线程中更新UI
        if threading.current_thread() is threading.main_thread():
            _update()
        else:
            self.root.after(0, _update)
        
    def handle_register(self):
        if not is_admin():
            messagebox.showerror("错误", "请以管理员权限运行此程序！")
            request_admin()
            return
            
        def register_thread():
            browser_manager = None
            try:
                self.update_status("=== 初始化程序 ===")
                # success, cursor_path = ExitCursor()
                # if not success:
                #     self.update_status("请先关闭 Cursor 后再试")
                #     return
                    
                self.update_status("正在重置设备信息...")
                # MachineIDResetter().reset_machine_ids()
                self.update_status("设备信息重置完成")
                
                if messagebox.askyesno("确认", "是否需要注册新账号？"):
                    self.update_status("\n开始注册账号")
                    self.update_status("正在初始化浏览器...")
                    
                    # 获取user_agent
                    user_agent = get_user_agent()
                    if not user_agent:
                        self.update_status("获取user agent失败，使用默认值")
                        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    
                    # 剔除user_agent中的"HeadlessChrome"
                    user_agent = user_agent.replace("HeadlessChrome", "Chrome")
                    
                    browser_manager = BrowserManager()
                    browser = browser_manager.init_browser(user_agent)
                    
                    self.update_status("正在初始化邮箱验证模块...")
                    self.email_handler = EmailVerificationHandler()
                    
                    self.update_status("\n=== 配置信息 ===")
                    login_url = "https://authenticator.cursor.sh"
                    sign_up_url = "https://authenticator.cursor.sh/sign-up"
                    settings_url = "https://www.cursor.com/settings"
                    
                    self.update_status("正在生成随机账号信息...")
                    email_generator = EmailGenerator()
                    account = email_generator.generate_email()
                    password = email_generator.default_password
                    first_name = email_generator.default_first_name
                    last_name = email_generator.default_last_name
                    
                    self.update_status(f"生成的邮箱账号: {account}")
                    
                    tab = browser.latest_tab
                    tab.run_js("try { turnstile.reset() } catch(e) { }")
                    
                    self.update_status("\n=== 开始注册流程 ===")
                    self.update_status(f"正在访问登录页面: {login_url}")
                    tab.get(login_url)
                    
                    if self.sign_up_account_ui(browser, tab, account, password, first_name, last_name, sign_up_url,settings_url):
                        self.update_status("注册成功")
                        # self.update_status("正在获取会话令牌...")
                        # token = get_cursor_session_token(tab)
                        # if token:
                        #     self.update_status("更新认证信息...")
                        #     update_cursor_auth(
                        #         email=account,
                        #         access_token=token,
                        #         refresh_token=token
                        #     )
                        #     self.update_status("认证信息更新完毕")
                        #     self.update_status("\n=== 注册成功 ===")
                        #     self.update_status(f"账号信息:\n邮箱: {account}\n密码: {password}")
                        # else:
                        #     self.update_status("获取会话令牌失败，注册流程未完成")
                    else:
                        self.update_status("注册失败")
                
                self.update_status("\n所有操作已完成")
                # if messagebox.askyesno("完成", "是否要重启 Cursor？"):
                #     self.restart_cursor(cursor_path)
                    
            except Exception as e:
                self.update_status(f"发生错误: {str(e)}")
                import traceback
                self.update_status(traceback.format_exc())
            finally:
                # 清理资源
                if browser_manager:
                    browser_manager.quit()
                
        threading.Thread(target=register_thread, daemon=True).start()
        
    def handle_reset(self):
        if not is_admin():
            messagebox.showerror("错误", "请以管理员权限运行此程序！")
            request_admin()
            return
            
        success, _ = ExitCursor()
        if success:
            MachineIDResetter().reset_machine_ids()
            self.update_status("文件或设备信息修改成功！")
        else:
            self.update_status("Cursor 未能自动关闭，请手动关闭后重试")
            
    def handle_restore(self):
        if not is_admin():
            messagebox.showerror("错误", "请以管理员权限运行此程序！")
            request_admin()
            return
            
        success, _ = ExitCursor()
        if success:
            MachineIDResetter().restore_machine_ids()
            self.update_status("文件或设备信息恢复成功！")
        else:
            self.update_status("Cursor 未能自动关闭，请手动关闭后重试")
            
    def restart_cursor(self, cursor_path):
        try:
            if os.name == 'nt':
                os.startfile(cursor_path)
            else:
                os.system(f'open "{cursor_path}"')
            self.root.quit()
        except Exception as e:
            self.update_status(f"重启 Cursor 失败: {str(e)}")
            
    def sign_up_account_ui(self, browser, tab, account, password, first_name, last_name, sign_up_url,settings_url):
        """UI版本的注册账号方法"""
        self.update_status(f"正在访问注册页面: {sign_up_url}")
        tab.get(sign_up_url)

        try:
            if tab.ele("@name=first_name"):
                self.update_status("正在填写个人信息...")
                tab.actions.click("@name=first_name").input(first_name)
                self.update_status(f"已输入名字: {first_name}")
                time.sleep(random.uniform(1, 3))

                tab.actions.click("@name=last_name").input(last_name)
                self.update_status(f"已输入姓氏: {last_name}")
                time.sleep(random.uniform(1, 3))

                tab.actions.click("@name=email").input(account)
                self.update_status(f"已输入邮箱: {account}")
                time.sleep(random.uniform(1, 3))

                self.update_status("提交个人信息...")
                tab.actions.click("@type=submit")

        except Exception as e:
            self.update_status(f"注册页面访问失败: {str(e)}")
            return False

        self.handle_turnstile(tab)

        try:
            if tab.ele("@name=password"):
                self.update_status("正在设置密码...")
                tab.ele("@name=password").input(password)
                time.sleep(random.uniform(1, 3))

                self.update_status("提交密码...")
                tab.ele("@type=submit").click()
                self.update_status("密码设置完成，等待系统响应...")

        except Exception as e:
            self.update_status(f"密码设置失败: {str(e)}")
            return False

        if tab.ele("This email is not available."):
            self.update_status("注册失败：邮箱已被使用")
            return False

        self.handle_turnstile(tab)

        while True:
            try:
                if tab.ele("Account Settings"):
                    self.update_status("注册成功 - 已进入账户设置页面")
                    break
                if tab.ele("@data-index=0"):
                    self.update_status("正在获取邮箱验证码...")
                    code = self.email_handler.get_verification_code()
                    if not code:
                        self.update_status("获取验证码失败")
                        return False

                    self.update_status(f"成功获取验证码: {code}")
                    self.update_status("正在输入验证码...")
                    i = 0
                    for digit in code:
                        tab.ele(f"@data-index={i}").input(digit)
                        time.sleep(random.uniform(0.1, 0.3))
                        i += 1
                    self.update_status("验证码输入完成")
                    break
            except Exception as e:
                self.update_status(f"验证码处理过程出错: {str(e)}")

        self.handle_turnstile(tab)
        wait_time = random.randint(3, 6)
        for i in range(wait_time):
            self.update_status(f"等待系统处理中... 剩余 {wait_time - i} 秒")
            time.sleep(1)

        # 获取账户信息
        self.update_status("正在获取账户信息...")
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
                self.update_status(f"账户可用额度上限: {total_usage}")
        except Exception as e:
            self.update_status(f"获取账户额度信息失败: {str(e)}")
        time.sleep(5)

        return True

    def handle_turnstile(self, tab):
        """处理Turnstile验证"""
        self.update_status("正在检测 Turnstile 验证...")
        try:
            while True:
                try:
                    challengeCheck = (
                        tab.ele("@id=cf-turnstile", timeout=2)
                        .child()
                        .shadow_root.ele("tag:iframe")
                        .ele("tag:body")
                        .sr("tag:input")
                    )

                    if challengeCheck:
                        self.update_status("检测到 Turnstile 验证，正在处理...")
                        time.sleep(random.uniform(1, 3))
                        challengeCheck.click()
                        time.sleep(2)
                        self.update_status("Turnstile 验证通过")
                        return True
                except:
                    pass

                if tab.ele("@name=password"):
                    self.update_status("验证成功 - 已到达密码输入页面")
                    break
                if tab.ele("@data-index=0"):
                    self.update_status("验证成功 - 已到达验证码输入页面")
                    break
                if tab.ele("Account Settings"):
                    self.update_status("验证成功 - 已到达账户设置页面")
                    break
                time.sleep(random.uniform(1, 2))
        except Exception as e:
            self.update_status(f"Turnstile 验证失败: {str(e)}")
            return False
        
    def run(self):
        try:
            logging.info("Starting main loop")
            self.root.mainloop()
        except Exception as e:
            logging.error(f"Runtime error: {str(e)}", exc_info=True)
            messagebox.showerror("错误", f"运行时错误: {str(e)}\n详细日志已保存到: {log_file}")
            sys.exit(1)

if __name__ == "__main__":
    try:
        app = CursorProUI()
        app.run()
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}", exc_info=True)
        messagebox.showerror("错误", f"致命错误: {str(e)}\n详细日志已保存到: {log_file}")
        sys.exit(1) 