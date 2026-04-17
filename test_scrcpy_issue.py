#!/usr/bin/env python3
"""
诊断Scrcpy启动问题
"""
import subprocess
import os
import sys
import time

def test_scrcpy_direct():
    """直接测试Scrcpy启动"""
    print("=" * 60)
    print("测试Scrcpy直接启动")
    print("=" * 60)
    
    scrcpy_path = r"D:\MyConfiguration\admin\AndroidStudioProjects\mi-tv-launcher\tv-launcher-app\backend_server\scrcpy\scrcpy.exe"
    tv_ip = "10.181.184.226"
    
    if not os.path.exists(scrcpy_path):
        print(f"错误: Scrcpy未找到: {scrcpy_path}")
        return False
    
    print(f"Scrcpy路径: {scrcpy_path}")
    print(f"电视IP: {tv_ip}")
    
    # 测试命令1: 基本启动
    cmd1 = [
        scrcpy_path,
        "--serial", f"{tv_ip}:5555",
        "--no-audio",
        "--max-fps", "15",
        "--max-size", "800",
        "--window-title", "小米电视远程控制"
    ]
    
    print(f"\n测试命令1: {' '.join(cmd1)}")
    
    try:
        process = subprocess.Popen(
            cmd1,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        
        print(f"Scrcpy进程已启动，PID: {process.pid}")
        print("等待5秒...")
        time.sleep(5)
        
        # 检查进程状态
        if process.poll() is None:
            print("✓ Scrcpy进程仍在运行")
            
            # 获取窗口信息
            print("\n检查窗口信息...")
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'create_time']):
                    if proc.info['pid'] == process.pid:
                        print(f"  进程信息: {proc.info}")
                        break
            except ImportError:
                print("  未安装psutil，跳过进程检查")
            
            # 停止进程
            print("\n停止Scrcpy...")
            process.terminate()
            try:
                process.wait(timeout=5)
                print("✓ Scrcpy正常停止")
            except subprocess.TimeoutExpired:
                process.kill()
                print("✗ Scrcpy强制停止")
            
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"✗ Scrcpy进程已退出")
            print(f"  退出码: {process.returncode}")
            print(f"  标准输出: {stdout[:200]}")
            print(f"  标准错误: {stderr[:500]}")
            return False
            
    except Exception as e:
        print(f"✗ 启动Scrcpy失败: {e}")
        return False

def test_scrcpy_with_adb_check():
    """测试Scrcpy并检查ADB连接"""
    print("\n" + "=" * 60)
    print("测试ADB连接状态")
    print("=" * 60)
    
    adb_path = r"D:\MyConfiguration\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    
    # 检查ADB设备
    try:
        result = subprocess.run([adb_path, "devices"], capture_output=True, text=True, timeout=10)
        print(f"ADB设备列表:\n{result.stdout}")
        
        if f"{tv_ip}:5555" in result.stdout and "device" in result.stdout:
            print("✓ 电视ADB连接正常")
        else:
            print("✗ 电视ADB连接异常")
            
    except Exception as e:
        print(f"✗ 检查ADB设备失败: {e}")

def test_backend_scrcpy_api():
    """测试后端Scrcpy API"""
    print("\n" + "=" * 60)
    print("测试后端Scrcpy API")
    print("=" * 60)
    
    import requests
    
    # 1. 检查Scrcpy安装状态
    print("1. 检查Scrcpy安装状态...")
    try:
        response = requests.get("http://localhost:8000/api/v1/scrcpy/check", timeout=5)
        print(f"  状态码: {response.status_code}")
        print(f"  响应: {response.json()}")
    except Exception as e:
        print(f"  ✗ 检查失败: {e}")
    
    # 2. 获取设备列表
    print("\n2. 获取设备列表...")
    try:
        response = requests.get("http://localhost:8000/api/v1/devices", timeout=5)
        if response.status_code == 200:
            devices = response.json()
            print(f"  找到 {len(devices)} 个设备")
            for device in devices:
                print(f"  设备: {device.get('device_name')} (ID: {device.get('id')}, IP: {device.get('eth_ip') or device.get('wifi_ip')})")
                if "10.181.184.226" in str(device.get('eth_ip')) or "10.181.184.226" in str(device.get('wifi_ip')):
                    device_id = device.get('id')
                    print(f"  ✓ 找到目标电视，设备ID: {device_id}")
                    return device_id
        else:
            print(f"  ✗ 获取设备失败: {response.status_code}")
    except Exception as e:
        print(f"  ✗ 获取设备失败: {e}")
    
    return None

def analyze_scrcpy_issue():
    """分析Scrcpy问题"""
    print("\n" + "=" * 60)
    print("问题分析")
    print("=" * 60)
    
    print("可能的问题原因:")
    print("1. Scrcpy启动参数不正确")
    print("2. 窗口被隐藏或最小化")
    print("3. 缺少必要的依赖库")
    print("4. 防火墙或安全软件阻止")
    print("5. 电视ADB授权问题")
    print("6. Scrcpy版本不兼容")
    
    print("\n建议的解决方案:")
    print("1. 使用 --always-on-top 参数确保窗口在前台")
    print("2. 使用 --window-borderless 无边框窗口")
    print("3. 使用 --window-x 和 --window-y 指定窗口位置")
    print("4. 检查Scrcpy日志输出")
    print("5. 尝试不同的分辨率设置")
    print("6. 确保电视已授权ADB调试")

def main():
    """主函数"""
    print("小米电视Scrcpy问题诊断工具")
    print("=" * 60)
    
    # 测试直接启动
    success = test_scrcpy_direct()
    
    # 测试ADB连接
    test_scrcpy_with_adb_check()
    
    # 测试后端API
    device_id = test_backend_scrcpy_api()
    
    # 分析问题
    analyze_scrcpy_issue()
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)
    
    if success:
        print("✓ Scrcpy可以直接启动")
        print("问题可能在于后端API的启动参数或窗口管理")
    else:
        print("✗ Scrcpy启动失败")
        print("需要检查Scrcpy安装和配置")
    
    if device_id:
        print(f"\n建议的测试命令:")
        scrcpy_path = r"D:\MyConfiguration\admin\AndroidStudioProjects\mi-tv-launcher\tv-launcher-app\backend_server\scrcpy\scrcpy.exe"
        cmd = f'"{scrcpy_path}" --serial 10.181.184.226:5555 --no-audio --max-fps 15 --max-size 800 --always-on-top --window-title "小米电视远程控制"'
        print(cmd)

if __name__ == "__main__":
    main()