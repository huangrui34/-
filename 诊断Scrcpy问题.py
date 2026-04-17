#!/usr/bin/env python3
"""
诊断Scrcpy启动后立即停止的问题
"""
import subprocess
import time
import os
import sys

def test_scrcpy_directly():
    """直接测试Scrcpy启动"""
    print("=" * 60)
    print("直接测试Scrcpy启动")
    print("=" * 60)
    
    scrcpy_path = r"D:\MyConfiguration\admin\AndroidStudioProjects\mi-tv-launcher\tv-launcher-app\backend_server\scrcpy\scrcpy.exe"
    tv_ip = "10.181.184.226"
    
    if not os.path.exists(scrcpy_path):
        print(f"✗ Scrcpy未找到: {scrcpy_path}")
        return False
    
    print(f"Scrcpy路径: {scrcpy_path}")
    print(f"电视IP: {tv_ip}")
    
    # 测试不同的启动参数
    test_cases = [
        {
            "name": "基本启动",
            "args": [
                scrcpy_path,
                "--serial", f"{tv_ip}:5555",
                "--no-audio",
                "--max-fps", "15",
                "--max-size", "800"
            ]
        },
        {
            "name": "带窗口参数",
            "args": [
                scrcpy_path,
                "--serial", f"{tv_ip}:5555",
                "--no-audio",
                "--max-fps", "15",
                "--max-size", "800",
                "--always-on-top",
                "--window-title", "测试窗口",
                "--window-borderless",
                "--window-x", "100",
                "--window-y", "100"
            ]
        },
        {
            "name": "简化参数",
            "args": [
                scrcpy_path,
                "--serial", f"{tv_ip}:5555",
                "--no-audio",
                "--max-size", "1024"
            ]
        },
        {
            "name": "最小参数",
            "args": [
                scrcpy_path,
                "--serial", f"{tv_ip}:5555"
            ]
        }
    ]
    
    for test_case in test_cases:
        print(f"\n测试: {test_case['name']}")
        print(f"命令: {' '.join(test_case['args'])}")
        
        try:
            process = subprocess.Popen(
                test_case['args'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            print(f"进程PID: {process.pid}")
            
            # 等待3秒检查进程状态
            time.sleep(3)
            
            if process.poll() is None:
                print(f"✓ Scrcpy仍在运行")
                
                # 获取输出
                try:
                    stdout, stderr = process.communicate(timeout=1)
                    print(f"  标准输出: {stdout[:200]}")
                    print(f"  标准错误: {stderr[:500]}")
                except:
                    pass
                
                # 停止进程
                process.terminate()
                try:
                    process.wait(timeout=3)
                    print(f"✓ Scrcpy正常停止")
                except:
                    process.kill()
                    print(f"✗ Scrcpy强制停止")
                
                return True
            else:
                stdout, stderr = process.communicate()
                print(f"✗ Scrcpy已退出")
                print(f"  退出码: {process.returncode}")
                print(f"  标准输出: {stdout[:500]}")
                print(f"  标准错误: {stderr[:500]}")
                
        except Exception as e:
            print(f"✗ 启动失败: {e}")
    
    return False

def check_adb_connection():
    """检查ADB连接"""
    print("\n" + "=" * 60)
    print("检查ADB连接")
    print("=" * 60)
    
    adb_path = r"D:\MyConfiguration\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    tv_ip = "10.181.184.226"
    
    try:
        # 检查ADB版本
        result = subprocess.run([adb_path, "--version"], capture_output=True, text=True, timeout=5)
        print(f"ADB版本检查: {'成功' if result.returncode == 0 else '失败'}")
        if result.returncode == 0:
            print(f"  版本信息: {result.stdout.splitlines()[0]}")
        
        # 检查设备连接
        result = subprocess.run([adb_path, "devices"], capture_output=True, text=True, timeout=10)
        print(f"\nADB设备列表:")
        print(result.stdout)
        
        if f"{tv_ip}:5555" in result.stdout and "device" in result.stdout:
            print(f"✓ 电视ADB连接正常")
            return True
        else:
            print(f"✗ 电视ADB连接异常")
            return False
            
    except Exception as e:
        print(f"✗ ADB检查失败: {e}")
        return False

def test_scrcpy_with_logging():
    """测试Scrcpy并记录日志"""
    print("\n" + "=" * 60)
    print("测试Scrcpy并记录详细日志")
    print("=" * 60)
    
    scrcpy_path = r"D:\MyConfiguration\admin\AndroidStudioProjects\mi-tv-launcher\tv-launcher-app\backend_server\scrcpy\scrcpy.exe"
    tv_ip = "10.181.184.226"
    
    # 创建日志文件
    log_file = "scrcpy_debug.log"
    
    cmd = [
        scrcpy_path,
        "--serial", f"{tv_ip}:5555",
        "--no-audio",
        "--max-fps", "15",
        "--max-size", "800",
        "--always-on-top",
        "--window-title", "Scrcpy调试",
        "--log-level", "debug"
    ]
    
    print(f"启动命令: {' '.join(cmd)}")
    print(f"日志文件: {log_file}")
    
    try:
        with open(log_file, "w", encoding="utf-8") as log:
            process = subprocess.Popen(
                cmd,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        
        print(f"Scrcpy进程PID: {process.pid}")
        
        # 等待并检查
        for i in range(5):
            time.sleep(1)
            if process.poll() is not None:
                print(f"✗ Scrcpy在第{i+1}秒退出")
                break
            else:
                print(f"  Scrcpy仍在运行 ({i+1}秒)")
        
        if process.poll() is None:
            print(f"✓ Scrcpy运行超过5秒")
            process.terminate()
            process.wait(timeout=3)
            print(f"✓ Scrcpy正常停止")
            
            # 读取日志
            with open(log_file, "r", encoding="utf-8") as f:
                log_content = f.read()
                print(f"\n日志内容:")
                print(log_content[:1000])
            
            return True
        else:
            print(f"✗ Scrcpy已退出，退出码: {process.returncode}")
            
            # 读取日志
            with open(log_file, "r", encoding="utf-8") as f:
                log_content = f.read()
                print(f"\n日志内容:")
                print(log_content)
            
            return False
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False

def analyze_scrcpy_issue():
    """分析Scrcpy问题"""
    print("\n" + "=" * 60)
    print("Scrcpy问题分析")
    print("=" * 60)
    
    print("可能的问题原因:")
    print("1. ADB连接不稳定")
    print("2. Scrcpy版本不兼容")
    print("3. 电视分辨率不支持")
    print("4. 缺少必要的依赖库")
    print("5. 防火墙或安全软件阻止")
    print("6. 电视ADB授权问题")
    
    print("\n建议的解决方案:")
    print("1. 检查ADB连接稳定性")
    print("2. 尝试不同的Scrcpy版本")
    print("3. 调整分辨率参数")
    print("4. 安装必要的运行库")
    print("5. 检查防火墙设置")
    print("6. 重新授权ADB调试")
    
    print("\n立即测试命令:")
    scrcpy_path = r"D:\MyConfiguration\admin\AndroidStudioProjects\mi-tv-launcher\tv-launcher-app\backend_server\scrcpy\scrcpy.exe"
    print(f'  "{scrcpy_path}" --serial 10.181.184.226:5555 --no-audio --max-size 1024 --log-level debug')

def main():
    """主函数"""
    print("Scrcpy启动问题诊断工具")
    print("=" * 60)
    
    # 检查ADB连接
    if not check_adb_connection():
        print("\n✗ ADB连接问题，请先解决ADB连接")
        return
    
    # 直接测试Scrcpy
    if test_scrcpy_directly():
        print("\n✓ Scrcpy可以直接启动")
        print("问题可能在于后端API的启动参数")
    else:
        print("\n✗ Scrcpy直接启动失败")
        print("需要进一步诊断")
    
    # 测试带日志的Scrcpy
    test_scrcpy_with_logging()
    
    # 分析问题
    analyze_scrcpy_issue()
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)

if __name__ == "__main__":
    main()