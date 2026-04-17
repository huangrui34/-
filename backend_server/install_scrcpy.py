#!/usr/bin/env python3
"""
Scrcpy自动安装脚本
此脚本会自动下载并安装Scrcpy到项目目录中
"""

import os
import sys
import zipfile
import tarfile
import platform
import subprocess
import urllib.request
import shutil
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
SCRCPY_DIR = PROJECT_ROOT / "scrcpy"
SCRCPY_VERSION = "v2.4"  # Scrcpy版本

def get_os_info():
    """获取操作系统信息"""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "windows":
        return "windows", "win64" if "64" in machine else "win32"
    elif system == "linux":
        return "linux", "linux64" if "64" in machine else "linux32"
    elif system == "darwin":
        return "macos", "macos"
    else:
        return "unknown", "unknown"

def download_file(url, dest_path):
    """下载文件"""
    print(f"正在下载: {url}")
    try:
        urllib.request.urlretrieve(url, dest_path)
        print(f"下载完成: {dest_path}")
        return True
    except Exception as e:
        print(f"下载失败: {e}")
        return False

def extract_zip(zip_path, extract_to):
    """解压ZIP文件"""
    print(f"正在解压: {zip_path}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        print(f"解压完成: {extract_to}")
        return True
    except Exception as e:
        print(f"解压失败: {e}")
        return False

def extract_tar_gz(tar_path, extract_to):
    """解压tar.gz文件"""
    print(f"正在解压: {tar_path}")
    try:
        with tarfile.open(tar_path, 'r:gz') as tar_ref:
            tar_ref.extractall(extract_to)
        print(f"解压完成: {extract_to}")
        return True
    except Exception as e:
        print(f"解压失败: {e}")
        return False

def install_scrcpy_windows():
    """在Windows上安装Scrcpy"""
    print("正在为Windows安装Scrcpy...")
    
    # Scrcpy Windows版本下载URL
    url = f"https://github.com/Genymobile/scrcpy/releases/download/{SCRCPY_VERSION}/scrcpy-win64-{SCRCPY_VERSION}.zip"
    zip_path = SCRCPY_DIR / f"scrcpy-win64-{SCRCPY_VERSION}.zip"
    
    # 下载
    if not download_file(url, zip_path):
        return False
    
    # 解压
    if not extract_zip(zip_path, SCRCPY_DIR):
        return False
    
    # 移动文件到正确位置
    extracted_dir = SCRCPY_DIR / f"scrcpy-win64-{SCRCPY_VERSION}"
    if extracted_dir.exists():
        # 移动所有文件到scrcpy目录
        for item in extracted_dir.iterdir():
            dest = SCRCPY_DIR / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        
        # 删除临时目录
        shutil.rmtree(extracted_dir)
    
    # 删除ZIP文件
    zip_path.unlink()
    
    return True

def install_scrcpy_linux():
    """在Linux上安装Scrcpy"""
    print("正在为Linux安装Scrcpy...")
    
    # 尝试使用包管理器安装
    try:
        print("尝试使用包管理器安装...")
        # 检查是apt还是yum
        if shutil.which("apt"):
            subprocess.run(["sudo", "apt", "update"], check=True)
            subprocess.run(["sudo", "apt", "install", "-y", "scrcpy"], check=True)
            return True
        elif shutil.which("yum"):
            subprocess.run(["sudo", "yum", "install", "-y", "scrcpy"], check=True)
            return True
        elif shutil.which("dnf"):
            subprocess.run(["sudo", "dnf", "install", "-y", "scrcpy"], check=True)
            return True
        elif shutil.which("pacman"):
            subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "scrcpy"], check=True)
            return True
    except Exception as e:
        print(f"包管理器安装失败: {e}")
        print("尝试手动下载安装...")
    
    # 手动下载
    url = f"https://github.com/Genymobile/scrcpy/releases/download/{SCRCPY_VERSION}/scrcpy-{SCRCPY_VERSION}.tar.gz"
    tar_path = SCRCPY_DIR / f"scrcpy-{SCRCPY_VERSION}.tar.gz"
    
    if not download_file(url, tar_path):
        return False
    
    if not extract_tar_gz(tar_path, SCRCPY_DIR):
        return False
    
    # 编译安装
    extracted_dir = SCRCPY_DIR / f"scrcpy-{SCRCPY_VERSION}"
    if extracted_dir.exists():
        try:
            # 进入目录并编译
            os.chdir(extracted_dir)
            subprocess.run(["meson", "setup", "build", "--buildtype=release", "--strip", "-Db_lto=true"], check=True)
            subprocess.run(["ninja", "-C", "build"], check=True)
            subprocess.run(["sudo", "ninja", "-C", "build", "install"], check=True)
            
            # 返回原目录
            os.chdir(PROJECT_ROOT)
            
            # 删除临时文件
            shutil.rmtree(extracted_dir)
            tar_path.unlink()
            
            return True
        except Exception as e:
            print(f"编译安装失败: {e}")
            return False
    
    return False

def install_scrcpy_macos():
    """在macOS上安装Scrcpy"""
    print("正在为macOS安装Scrcpy...")
    
    # 尝试使用Homebrew安装
    try:
        print("尝试使用Homebrew安装...")
        if shutil.which("brew"):
            subprocess.run(["brew", "install", "scrcpy"], check=True)
            return True
    except Exception as e:
        print(f"Homebrew安装失败: {e}")
    
    # 手动下载
    url = f"https://github.com/Genymobile/scrcpy/releases/download/{SCRCPY_VERSION}/scrcpy-{SCRCPY_VERSION}.tar.gz"
    tar_path = SCRCPY_DIR / f"scrcpy-{SCRCPY_VERSION}.tar.gz"
    
    if not download_file(url, tar_path):
        return False
    
    if not extract_tar_gz(tar_path, SCRCPY_DIR):
        return False
    
    # 编译安装
    extracted_dir = SCRCPY_DIR / f"scrcpy-{SCRCPY_VERSION}"
    if extracted_dir.exists():
        try:
            # 进入目录并编译
            os.chdir(extracted_dir)
            subprocess.run(["meson", "setup", "build", "--buildtype=release", "--strip", "-Db_lto=true"], check=True)
            subprocess.run(["ninja", "-C", "build"], check=True)
            subprocess.run(["sudo", "ninja", "-C", "build", "install"], check=True)
            
            # 返回原目录
            os.chdir(PROJECT_ROOT)
            
            # 删除临时文件
            shutil.rmtree(extracted_dir)
            tar_path.unlink()
            
            return True
        except Exception as e:
            print(f"编译安装失败: {e}")
            return False
    
    return False

def check_scrcpy_installed():
    """检查Scrcpy是否已安装"""
    # 检查系统PATH中是否有scrcpy
    if shutil.which("scrcpy"):
        return True
    
    # 检查项目目录中是否有scrcpy
    if (SCRCPY_DIR / "scrcpy.exe").exists() or (SCRCPY_DIR / "scrcpy").exists():
        return True
    
    return False

def main():
    """主函数"""
    print("=" * 60)
    print("Scrcpy自动安装脚本")
    print("=" * 60)
    
    # 创建scrcpy目录
    SCRCPY_DIR.mkdir(exist_ok=True)
    
    # 检查是否已安装
    if check_scrcpy_installed():
        print("Scrcpy已安装，跳过安装步骤")
        return True
    
    # 获取操作系统信息
    os_name, os_arch = get_os_info()
    print(f"检测到操作系统: {os_name} ({os_arch})")
    
    # 根据操作系统安装
    success = False
    if os_name == "windows":
        success = install_scrcpy_windows()
    elif os_name == "linux":
        success = install_scrcpy_linux()
    elif os_name == "macos":
        success = install_scrcpy_macos()
    else:
        print(f"不支持的操作系统: {os_name}")
        return False
    
    if success:
        print("=" * 60)
        print("Scrcpy安装成功！")
        print(f"安装目录: {SCRCPY_DIR}")
        print("=" * 60)
        
        # 测试安装
        print("测试Scrcpy安装...")
        try:
            if os_name == "windows":
                scrcpy_exe = SCRCPY_DIR / "scrcpy.exe"
                if scrcpy_exe.exists():
                    result = subprocess.run([str(scrcpy_exe), "--version"], capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"Scrcpy版本: {result.stdout.strip()}")
                    else:
                        print("Scrcpy测试失败")
            else:
                result = subprocess.run(["scrcpy", "--version"], capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"Scrcpy版本: {result.stdout.strip()}")
                else:
                    print("Scrcpy测试失败")
        except Exception as e:
            print(f"测试时出错: {e}")
        
        return True
    else:
        print("=" * 60)
        print("Scrcpy安装失败！")
        print("请手动安装Scrcpy:")
        print("1. 访问: https://github.com/Genymobile/scrcpy/releases")
        print(f"2. 下载 {SCRCPY_VERSION} 版本")
        print(f"3. 解压到: {SCRCPY_DIR}")
        print("=" * 60)
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n安装被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"安装过程中出现错误: {e}")
        sys.exit(1)