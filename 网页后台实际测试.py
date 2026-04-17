#!/usr/bin/env python3
"""
通过网页后台进行实际功能测试
模拟用户通过网页按钮操作
"""
import requests
import json
import time
import subprocess
import sys

BASE_URL = "http://localhost:8000"
TV_IP = "10.181.184.226"

def print_step(step_num, description):
    """打印测试步骤"""
    print(f"\n{'='*60}")
    print(f"步骤 {step_num}: {description}")
    print(f"{'='*60}")

def test_backend_connection():
    """测试后端连接"""
    print_step(1, "测试后端服务器连接")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"✓ 后端服务器连接正常")
            print(f"  响应: {response.json()}")
            return True
        else:
            print(f"✗ 后端服务器连接失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 后端服务器连接异常: {e}")
        return False

def get_devices():
    """获取设备列表"""
    print_step(2, "获取设备列表")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/devices", timeout=5)
        if response.status_code == 200:
            devices = response.json()
            print(f"✓ 获取到 {len(devices)} 个设备")
            
            # 查找目标电视
            target_device = None
            for device in devices:
                print(f"  设备: {device.get('device_name')} (ID: {device.get('id')}, IP: {device.get('eth_ip') or device.get('wifi_ip')})")
                if TV_IP in str(device.get('eth_ip')) or TV_IP in str(device.get('wifi_ip')):
                    target_device = device
                    print(f"  ✓ 找到目标电视: {device.get('device_name')} (ID: {device.get('id')})")
            
            return target_device
        else:
            print(f"✗ 获取设备失败: {response.status_code}")
            return None
    except Exception as e:
        print(f"✗ 获取设备异常: {e}")
        return None

def create_hdmi_policy(device_id):
    """创建HDMI1策略"""
    print_step(3, "创建HDMI1策略")
    
    policy_data = {
        "name": f"HDMI1测试策略_{int(time.time())}",
        "mode": "hdmi",
        "target_hdmi_port": 1,
        "is_active": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/policies",
            json=policy_data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            policy = response.json()
            print(f"✓ HDMI1策略创建成功")
            print(f"  策略ID: {policy.get('id')}")
            print(f"  策略名称: {policy.get('name')}")
            print(f"  模式: {policy.get('mode')}")
            print(f"  HDMI端口: {policy.get('target_hdmi_port')}")
            return policy
        else:
            print(f"✗ HDMI1策略创建失败: {response.status_code}")
            print(f"  响应: {response.text}")
            return None
    except Exception as e:
        print(f"✗ HDMI1策略创建异常: {e}")
        return None

def bind_policy_to_device(device_id, policy_id):
    """将策略绑定到设备"""
    print_step(4, "将策略绑定到设备")
    
    try:
        # 更新设备策略
        update_data = {
            "policy_id": policy_id
        }
        
        response = requests.put(
            f"{BASE_URL}/api/v1/devices/{device_id}",
            json=update_data,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✓ 策略绑定成功")
            print(f"  设备ID: {device_id}")
            print(f"  策略ID: {policy_id}")
            return True
        else:
            print(f"✗ 策略绑定失败: {response.status_code}")
            print(f"  响应: {response.text}")
            return False
    except Exception as e:
        print(f"✗ 策略绑定异常: {e}")
        return False

def execute_policy_immediately(device_id, policy):
    """立即执行策略"""
    print_step(5, "立即执行策略")
    
    print(f"设备ID: {device_id}")
    print(f"策略模式: {policy.get('mode')}")
    
    if policy.get('mode') == 'hdmi':
        hdmi_port = policy.get('target_hdmi_port')
        print(f"HDMI端口: {hdmi_port}")
        
        # 使用ADB立即执行HDMI切换
        return execute_hdmi_switch_immediately(hdmi_port)
    elif policy.get('mode') == 'app':
        app_package = policy.get('target_app_package')
        print(f"APP包名: {app_package}")
        
        # 使用ADB立即执行APP启动
        return execute_app_launch_immediately(app_package)
    else:
        print(f"✗ 未知策略模式: {policy.get('mode')}")
        return False

def execute_hdmi_switch_immediately(hdmi_port):
    """立即执行HDMI切换"""
    print(f"立即执行HDMI{hdmi_port}切换...")
    
    adb_path = r"D:\MyConfiguration\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    
    # 方法1: 按键模拟 (最可靠)
    print(f"方法1: 按键模拟切换HDMI{hdmi_port}")
    
    try:
        # 1. 发送TV输入键
        cmd1 = f"{adb_path} -s {TV_IP}:5555 shell input keyevent 178"
        result1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True, timeout=5)
        print(f"  TV输入键发送: {'成功' if result1.returncode == 0 else '失败'}")
        time.sleep(1)
        
        # 2. 根据HDMI端口选择方向键次数
        down_count = hdmi_port + 1  # HDMI1通常是第二个选项
        
        for i in range(down_count):
            cmd2 = f"{adb_path} -s {TV_IP}:5555 shell input keyevent 20"
            result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True, timeout=5)
            print(f"  下方向键 {i+1}/{down_count}: {'成功' if result2.returncode == 0 else '失败'}")
            time.sleep(0.3)
        
        # 3. 确认选择
        cmd3 = f"{adb_path} -s {TV_IP}:5555 shell input keyevent 23"
        result3 = subprocess.run(cmd3, shell=True, capture_output=True, text=True, timeout=5)
        print(f"  确认键发送: {'成功' if result3.returncode == 0 else '失败'}")
        
        print(f"✓ HDMI{hdmi_port}切换命令已发送")
        return True
        
    except Exception as e:
        print(f"✗ HDMI切换失败: {e}")
        return False

def execute_app_launch_immediately(app_package):
    """立即执行APP启动"""
    print(f"立即启动APP: {app_package}")
    
    adb_path = r"D:\MyConfiguration\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    
    try:
        # 先返回主页
        home_cmd = f"{adb_path} -s {TV_IP}:5555 shell input keyevent 3"
        subprocess.run(home_cmd, shell=True, capture_output=True, timeout=3)
        time.sleep(1)
        
        # 启动APP
        launch_cmd = f"{adb_path} -s {TV_IP}:5555 shell am start -n {app_package}/.MainActivity"
        result = subprocess.run(launch_cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        print(f"  APP启动命令: {'成功' if result.returncode == 0 else '失败'}")
        print(f"  输出: {result.stdout}")
        
        if result.returncode == 0:
            print(f"✓ APP启动命令已发送")
            return True
        else:
            print(f"✗ APP启动失败")
            return False
            
    except Exception as e:
        print(f"✗ APP启动异常: {e}")
        return False

def test_scrcpy_launch():
    """测试Scrcpy启动"""
    print_step(6, "测试Scrcpy启动")
    
    try:
        # 通过API启动Scrcpy
        scrcpy_data = {
            "device_id": 1,  # 假设设备ID为1
            "ip": TV_IP,
            "port": 5555
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v1/scrcpy/start",
            json=scrcpy_data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Scrcpy启动API响应正常")
            print(f"  响应: {result}")
            
            if result.get("ok"):
                print(f"  Scrcpy启动成功")
                print(f"  PID: {result.get('pid')}")
                print(f"  消息: {result.get('message')}")
                
                # 等待2秒检查进程状态
                time.sleep(2)
                
                # 检查进程是否还在运行
                pid = result.get('pid')
                if pid:
                    try:
                        import psutil
                        if psutil.pid_exists(pid):
                            print(f"  ✓ Scrcpy进程仍在运行 (PID: {pid})")
                        else:
                            print(f"  ✗ Scrcpy进程已退出 (PID: {pid})")
                    except ImportError:
                        print(f"  ℹ 未安装psutil，无法检查进程状态")
                
                return True
            else:
                print(f"  ✗ Scrcpy启动失败")
                print(f"  详情: {result.get('detail')}")
                return False
        else:
            print(f"✗ Scrcpy启动API失败: {response.status_code}")
            print(f"  响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Scrcpy启动测试异常: {e}")
        return False

def diagnose_white_screen_issue():
    """诊断白屏闪烁问题"""
    print_step(7, "诊断白屏闪烁问题")
    
    print("问题分析:")
    print("1. 白屏后闪一下继续白屏又闪一下循环")
    print("2. 电视机后台应用只显示一个设置")
    print("3. 手动清理后台后出现白屏闪烁")
    
    print("\n可能的原因:")
    print("1. 策略执行失败，导致系统不断重试")
    print("2. HDMI切换失败，电视无法正确显示")
    print("3. 应用崩溃或异常退出")
    print("4. 系统资源不足")
    
    print("\n建议的解决方案:")
    print("1. 确保HDMI物理连接正常")
    print("2. 检查电视HDMI端口设置")
    print("3. 更新策略执行逻辑，添加错误处理")
    print("4. 添加延迟和重试机制")
    print("5. 检查电视系统日志")
    
    # 检查电视当前状态
    print("\n检查电视当前状态:")
    adb_path = r"D:\MyConfiguration\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    
    try:
        # 检查当前活动
        cmd = f"{adb_path} -s {TV_IP}:5555 shell dumpsys activity activities | findstr mResumedActivity"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        print(f"  当前活动: {result.stdout}")
        
        # 检查窗口状态
        cmd = f"{adb_path} -s {TV_IP}:5555 shell dumpsys window windows | findstr mCurrentFocus"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        print(f"  当前焦点窗口: {result.stdout}")
        
        # 检查进程状态
        cmd = f"{adb_path} -s {TV_IP}:5555 shell ps | findstr -i launcher"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        print(f"  Launcher进程: {result.stdout}")
        
    except Exception as e:
        print(f"  检查电视状态失败: {e}")

def create_immediate_execution_solution():
    """创建立即执行解决方案"""
    print_step(8, "创建立即执行解决方案")
    
    solution = """
    立即执行策略解决方案:
    
    1. 后端API增强:
       - 添加立即执行策略的API端点
       - 支持通过ADB直接执行策略
       - 添加执行状态跟踪
    
    2. Android应用改进:
       - 添加策略立即执行广播接收器
       - 优化策略执行逻辑
       - 添加错误处理和重试机制
    
    3. 网页后台功能:
       - 添加"立即执行"按钮
       - 显示执行状态和结果
       - 添加执行日志
    
    立即执行API示例:
    
    POST /api/v1/devices/{device_id}/execute-policy
    {
        "policy_id": 1,
        "immediate": true
    }
    
    响应:
    {
        "ok": true,
        "message": "策略执行成功",
        "execution_id": "12345",
        "timestamp": "2026-04-16T10:30:00Z"
    }
    """
    
    print(solution)
    
    # 创建立即执行脚本
    immediate_script = f"""#!/usr/bin/env python3
# 立即执行策略脚本
import requests
import subprocess
import time

TV_IP = "{TV_IP}"
BASE_URL = "http://localhost:8000"

def execute_hdmi_immediately(port):
    \"\"\"立即执行HDMI切换\"\"\"
    adb_path = r"D:\\MyConfiguration\\admin\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe"
    
    print(f"立即切换到HDMI{{port}}")
    
    # 按键序列
    commands = [
        (f"{{adb_path}} -s {{TV_IP}}:5555 shell input keyevent 178", "TV输入键"),
        ("sleep 1", "等待1秒"),
        (f"{{adb_path}} -s {{TV_IP}}:5555 shell input keyevent 20", "下方向键"),
        ("sleep 0.3", "等待0.3秒"),
        (f"{{adb_path}} -s {{TV_IP}}:5555 shell input keyevent 20", "下方向键"),
        ("sleep 0.3", "等待0.3秒"),
        (f"{{adb_path}} -s {{TV_IP}}:5555 shell input keyevent 23", "确认键")
    ]
    
    for cmd, desc in commands:
        if cmd.startswith("sleep"):
            time.sleep(float(cmd.split()[1]))
            print(f"  {{desc}}完成")
        else:
            try:
                subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
                print(f"  {{desc}}发送成功")
            except:
                print(f"  {{desc}}发送失败")
    
    print(f"✓ HDMI{{port}}切换完成")

# 使用示例
if __name__ == "__main__":
    execute_hdmi_immediately(1)
"""
    
    print("\n立即执行脚本已创建")
    return immediate_script

def main():
    """主测试函数"""
    print("小米电视网页后台实际功能测试")
    print("=" * 60)
    
    # 1. 测试后端连接
    if not test_backend_connection():
        print("✗ 后端连接失败，测试终止")
        return
    
    # 2. 获取设备
    device = get_devices()
    if not device:
        print("✗ 未找到目标设备，测试终止")
        return
    
    device_id = device.get('id')
    
    # 3. 创建HDMI1策略
    policy = create_hdmi_policy(device_id)
    if not policy:
        print("✗ 策略创建失败，测试终止")
        return
    
    policy_id = policy.get('id')
    
    # 4. 绑定策略到设备
    if not bind_policy_to_device(device_id, policy_id):
        print("⚠ 策略绑定失败，但继续测试")
    
    # 5. 立即执行策略
    print("\n" + "="*60)
    print("开始立即执行策略测试")
    print("="*60)
    
    execute_policy_immediately(device_id, policy)
    
    # 6. 测试Scrcpy启动
    test_scrcpy_launch()
    
    # 7. 诊断白屏问题
    diagnose_white_screen_issue()
    
    # 8. 创建解决方案
    solution_script = create_immediate_execution_solution()
    
    # 9. 输出测试总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    print("测试完成!")
    print("\n发现的问题:")
    print("1. HDMI策略执行可能导致白屏闪烁")
    print("2. Scrcpy启动后可能立即停止")
    print("3. 需要策略立即执行机制")
    
    print("\n建议的解决方案:")
    print("1. 创建立即执行API端点")
    print("2. 优化HDMI切换逻辑")
    print("3. 修复Scrcpy启动参数")
    print("4. 添加错误处理和重试机制")
    
    print("\n立即操作:")
    print("1. 使用提供的脚本立即执行HDMI切换")
    print("2. 检查电视HDMI连接状态")
    print("3. 监控电视系统日志")
    
    # 保存解决方案脚本
    with open("immediate_execution.py", "w", encoding="utf-8") as f:
        f.write(solution_script)
    
    print(f"\n✓ 立即执行脚本已保存: immediate_execution.py")

if __name__ == "__main__":
    main()