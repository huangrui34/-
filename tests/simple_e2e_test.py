"""
简单的端到端测试
测试系统基本功能
"""
import subprocess
import time
import sys
import os

def check_adb_connection():
    """检查ADB连接"""
    print("检查ADB连接...")
    
    # 查找ADB
    adb_path = None
    possible_paths = [
        "D:\\MyConfiguration\\admin\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe",
        "adb.exe",
        "adb"
    ]
    
    for path in possible_paths:
        try:
            result = subprocess.run([path, "--version"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                adb_path = path
                print(f"找到ADB: {path}")
                break
        except:
            continue
    
    if not adb_path:
        print("错误: 未找到ADB")
        return False
    
    # 尝试连接到电视
    tv_ip = "10.181.184.226"
    print(f"尝试连接到电视: {tv_ip}")
    
    try:
        result = subprocess.run([adb_path, "connect", tv_ip], 
                              capture_output=True, text=True, timeout=10)
        print(f"连接结果: {result.stdout}")
        
        if "connected" in result.stdout or "already connected" in result.stdout:
            print("✓ ADB连接成功")
            return True
        else:
            print(f"✗ ADB连接失败: {result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ ADB连接超时")
        return False
    except Exception as e:
        print(f"✗ ADB连接异常: {e}")
        return False

def check_backend_server():
    """检查后端服务器"""
    print("\n检查后端服务器...")
    
    try:
        import requests
        import socket
        
        # 检查端口是否开放
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 8000))
        sock.close()
        
        if result == 0:
            print("✓ 后端服务器端口8000已开放")
            
            # 尝试访问API
            try:
                response = requests.get('http://localhost:8000/docs', timeout=5)
                if response.status_code == 200:
                    print("✓ 后端API文档可访问")
                    return True
                else:
                    print(f"✗ 后端API文档返回状态码: {response.status_code}")
                    return False
            except requests.exceptions.RequestException as e:
                print(f"✗ 无法访问后端API: {e}")
                return False
        else:
            print("✗ 后端服务器端口8000未开放")
            return False
    except ImportError:
        print("✗ 未安装requests库")
        return False
    except Exception as e:
        print(f"✗ 检查后端服务器时出错: {e}")
        return False

def check_project_structure():
    """检查项目结构"""
    print("\n检查项目结构...")
    
    required_dirs = [
        "backend_server",
        "backend_server/app",
        "tests",
        "tests/unit",
        "tests/integration",
        "tests/e2e"
    ]
    
    required_files = [
        "backend_server/app/main.py",
        "backend_server/app/models.py",
        "tests/conftest.py",
        "tests/test_utils.py"
    ]
    
    all_ok = True
    
    for dir_path in required_dirs:
        if os.path.isdir(dir_path):
            print(f"✓ 目录存在: {dir_path}")
        else:
            print(f"✗ 目录不存在: {dir_path}")
            all_ok = False
    
    for file_path in required_files:
        if os.path.isfile(file_path):
            print(f"✓ 文件存在: {file_path}")
        else:
            print(f"✗ 文件不存在: {file_path}")
            all_ok = False
    
    return all_ok

def run_unit_tests():
    """运行单元测试"""
    print("\n运行单元测试...")
    
    try:
        import pytest
        
        # 运行简化的单元测试
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/unit/backend/test_models_simple.py", "-v"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print("单元测试输出:")
        print(result.stdout)
        
        if result.returncode == 0:
            print("✓ 单元测试通过")
            return True
        else:
            print("✗ 单元测试失败")
            print("错误输出:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"✗ 运行单元测试时出错: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("小米电视启动器项目 - 端到端测试")
    print("=" * 60)
    
    test_results = []
    
    # 1. 检查项目结构
    test_results.append(("项目结构", check_project_structure()))
    
    # 2. 检查后端服务器
    test_results.append(("后端服务器", check_backend_server()))
    
    # 3. 检查ADB连接
    test_results.append(("ADB连接", check_adb_connection()))
    
    # 4. 运行单元测试
    test_results.append(("单元测试", run_unit_tests()))
    
    # 输出测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("✓ 所有测试通过!")
        return 0
    else:
        print("✗ 部分测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())