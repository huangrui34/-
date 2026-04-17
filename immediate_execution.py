#!/usr/bin/env python3
# 立即执行策略脚本
import requests
import subprocess
import time

TV_IP = "10.181.184.226"
BASE_URL = "http://localhost:8000"

def execute_hdmi_immediately(port):
    """立即执行HDMI切换"""
    adb_path = r"D:\MyConfiguration\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    
    print(f"立即切换到HDMI{port}")
    
    # 按键序列
    commands = [
        (f"{adb_path} -s {TV_IP}:5555 shell input keyevent 178", "TV输入键"),
        ("sleep 1", "等待1秒"),
        (f"{adb_path} -s {TV_IP}:5555 shell input keyevent 20", "下方向键"),
        ("sleep 0.3", "等待0.3秒"),
        (f"{adb_path} -s {TV_IP}:5555 shell input keyevent 20", "下方向键"),
        ("sleep 0.3", "等待0.3秒"),
        (f"{adb_path} -s {TV_IP}:5555 shell input keyevent 23", "确认键")
    ]
    
    for cmd, desc in commands:
        if cmd.startswith("sleep"):
            time.sleep(float(cmd.split()[1]))
            print(f"  {desc}完成")
        else:
            try:
                subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
                print(f"  {desc}发送成功")
            except:
                print(f"  {desc}发送失败")
    
    print(f"✓ HDMI{port}切换完成")

# 使用示例
if __name__ == "__main__":
    execute_hdmi_immediately(1)
