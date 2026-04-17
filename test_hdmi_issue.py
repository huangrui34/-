#!/usr/bin/env python3
"""
诊断HDMI切换问题
"""
import subprocess
import time

def test_hdmi_switching():
    """测试HDMI切换"""
    print("=" * 60)
    print("测试HDMI切换功能")
    print("=" * 60)
    
    adb_path = r"D:\MyConfiguration\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    tv_ip = "10.181.184.226"
    
    # 1. 测试小米电视HDMI切换方法
    print("\n1. 测试小米电视HDMI切换方法")
    
    # 方法1: 使用小米电视的HDMI切换intent
    hdmi_methods = [
        # 小米电视HDMI1
        ("am start -a android.intent.action.VIEW -d 'ext://com.mitv.tvhome/com.mitv.tvhome.ExternalSourceActivity?source=HDMI1'"),
        # 小米电视HDMI2  
        ("am start -a android.intent.action.VIEW -d 'ext://com.mitv.tvhome/com.mitv.tvhome.ExternalSourceActivity?source=HDMI2'"),
        # 通用HDMI切换
        ("am start -a android.settings.HDMI_SETTINGS"),
        # 显示设置
        ("am start -a android.settings.DISPLAY_SETTINGS"),
        # 输入源选择
        ("am start -a android.settings.INPUT_METHOD_SETTINGS"),
    ]
    
    for i, method in enumerate(hdmi_methods):
        print(f"\n尝试方法 {i+1}: {method}")
        try:
            cmd = f"{adb_path} -s {tv_ip}:5555 shell {method}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            print(f"  输出: {result.stdout[:200]}")
            if result.stderr:
                print(f"  错误: {result.stderr[:200]}")
            
            # 等待2秒查看效果
            time.sleep(2)
            
        except Exception as e:
            print(f"  执行失败: {e}")
    
    # 2. 测试按键模拟切换HDMI
    print("\n2. 测试按键模拟切换HDMI")
    
    # 小米电视遥控器按键码
    keycodes = {
        "HOME": "3",
        "BACK": "4",
        "DPAD_CENTER": "23",
        "DPAD_UP": "19",
        "DPAD_DOWN": "20",
        "DPAD_LEFT": "21",
        "DPAD_RIGHT": "22",
        "MENU": "82",
        "TV_INPUT": "178",  # TV/视频输入键
        "TV_POWER": "177",  # TV电源键
        "TV_INPUT_HDMI_1": "243",  # HDMI1
        "TV_INPUT_HDMI_2": "244",  # HDMI2
    }
    
    # 尝试发送HDMI切换按键
    for key_name, keycode in [("TV_INPUT", "178"), ("TV_INPUT_HDMI_1", "243")]:
        print(f"\n发送按键: {key_name} (code: {keycode})")
        try:
            cmd = f"{adb_path} -s {tv_ip}:5555 shell input keyevent {keycode}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            print(f"  按键发送成功")
            time.sleep(1)
        except Exception as e:
            print(f"  发送失败: {e}")
    
    # 3. 检查当前显示状态
    print("\n3. 检查当前显示状态")
    try:
        # 检查当前活动
        cmd = f"{adb_path} -s {tv_ip}:5555 shell dumpsys activity activities | findstr mResumedActivity"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        print(f"  当前活动: {result.stdout}")
        
        # 检查窗口状态
        cmd = f"{adb_path} -s {tv_ip}:5555 shell dumpsys window windows | findstr mCurrentFocus"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        print(f"  当前焦点窗口: {result.stdout}")
        
    except Exception as e:
        print(f"  检查失败: {e}")
    
    # 4. 测试通过设置切换
    print("\n4. 测试通过设置切换")
    try:
        # 打开设置
        cmd = f"{adb_path} -s {tv_ip}:5555 shell am start -a android.settings.SETTINGS"
        subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        print("  已打开设置")
        time.sleep(2)
        
        # 尝试导航到显示设置
        # 发送下键
        cmd = f"{adb_path} -s {tv_ip}:5555 shell input keyevent 20"
        subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
        time.sleep(1)
        
        # 发送确认键
        cmd = f"{adb_path} -s {tv_ip}:5555 shell input keyevent 23"
        subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
        time.sleep(1)
        
    except Exception as e:
        print(f"  设置切换失败: {e}")

def analyze_hdmi_issue():
    """分析HDMI问题"""
    print("\n" + "=" * 60)
    print("HDMI切换问题分析")
    print("=" * 60)
    
    print("可能的问题原因:")
    print("1. 权限不足: 需要系统权限才能切换HDMI")
    print("2. 小米电视定制: 需要使用小米特定的intent或服务")
    print("3. 按键码不正确: 需要正确的HDMI切换按键码")
    print("4. HDMI端口未连接设备: HDMI1可能没有连接设备")
    print("5. 电视固件限制: 某些电视固件限制HDMI切换")
    
    print("\n建议的解决方案:")
    print("1. 使用小米电视的特定intent: 'com.mitv.tvhome.ExternalSourceActivity'")
    print("2. 获取系统权限或使用root权限")
    print("3. 使用无障碍服务模拟操作")
    print("4. 使用ADB shell命令直接调用系统服务")
    print("5. 检查HDMI物理连接")
    
    print("\n小米电视HDMI切换参考:")
    print("- 包名: com.mitv.tvhome")
    print("- 活动: com.mitv.tvhome.ExternalSourceActivity")
    print("- 参数: source=HDMI1, source=HDMI2, source=HDMI3")
    print("- Intent: am start -a android.intent.action.VIEW -d 'ext://com.mitv.tvhome/com.mitv.tvhome.ExternalSourceActivity?source=HDMI1'")

def test_app_switching():
    """测试APP切换"""
    print("\n" + "=" * 60)
    print("测试APP切换功能")
    print("=" * 60)
    
    adb_path = r"D:\MyConfiguration\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    tv_ip = "10.181.184.226"
    app_package = "com.tcly.sharescreen"
    
    print(f"测试APP: {app_package}")
    
    # 1. 检查APP是否安装
    try:
        cmd = f"{adb_path} -s {tv_ip}:5555 shell pm list packages | findstr {app_package}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if app_package in result.stdout:
            print(f"✓ APP已安装: {app_package}")
        else:
            print(f"✗ APP未安装: {app_package}")
            return
    except Exception as e:
        print(f"✗ 检查APP失败: {e}")
        return
    
    # 2. 获取APP的主活动
    try:
        cmd = f"{adb_path} -s {tv_ip}:5555 shell dumpsys package {app_package} | findstr -A 5 -B 5 MAIN"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        print(f"APP活动信息:\n{result.stdout[:500]}")
    except Exception as e:
        print(f"获取活动信息失败: {e}")
    
    # 3. 启动APP
    print(f"\n启动APP: {app_package}")
    try:
        # 尝试不同的启动方式
        launch_methods = [
            f"am start -n {app_package}/.MainActivity",
            f"am start -n {app_package}/.activity.MainActivity",
            f"am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n {app_package}/.MainActivity",
            f"monkey -p {app_package} -c android.intent.category.LAUNCHER 1"
        ]
        
        for i, method in enumerate(launch_methods):
            print(f"\n尝试启动方式 {i+1}: {method}")
            cmd = f"{adb_path} -s {tv_ip}:5555 shell {method}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            print(f"  输出: {result.stdout}")
            if result.stderr:
                print(f"  错误: {result.stderr[:200]}")
            
            time.sleep(2)
            
            # 检查是否启动成功
            cmd = f"{adb_path} -s {tv_ip}:5555 shell dumpsys window windows | findstr mCurrentFocus"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if app_package in result.stdout:
                print(f"  ✓ APP启动成功!")
                break
            else:
                print(f"  ✗ APP未在前台")
    
    except Exception as e:
        print(f"启动APP失败: {e}")

def main():
    """主函数"""
    print("小米电视HDMI和APP切换问题诊断")
    print("=" * 60)
    
    # 测试APP切换
    test_app_switching()
    
    # 测试HDMI切换
    test_hdmi_switching()
    
    # 分析问题
    analyze_hdmi_issue()
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)
    print("建议:")
    print("1. 对于APP切换: 使用正确的活动名启动APP")
    print("2. 对于HDMI切换: 使用小米电视特定intent或按键模拟")
    print("3. 检查权限和连接状态")
    print("4. 考虑使用无障碍服务进行复杂操作")

if __name__ == "__main__":
    main()