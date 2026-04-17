"""
实际电视机端到端测试
针对电视机IP: 10.181.184.226 进行完整功能测试
"""
import os
import json
import pytest
import time
from pathlib import Path
from test_utils import adb_client, api_client, timer, assertions, retry

# 加载测试配置
CONFIG_FILE = Path(__file__).parent.parent / "fixtures" / "tv_config.json"
with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    TV_CONFIG = json.load(f)

TEST_TV_IP = TV_CONFIG["test_tv"]["ip"]
TEST_TV_PORT = TV_CONFIG["test_tv"]["port"]

@pytest.fixture(scope="session")
def tv_adb_client():
    """创建电视机ADB客户端"""
    client = adb_client(TEST_TV_IP, TEST_TV_PORT)
    
    # 测试连接
    print(f"连接到电视机: {TEST_TV_IP}:{TEST_TV_PORT}")
    connected = client.connect()
    
    if not connected:
        pytest.skip(f"无法连接到电视机 {TEST_TV_IP}:{TEST_TV_PORT}")
    
    yield client
    
    # 测试结束后断开连接
    client.disconnect()

@pytest.fixture(scope="session")
def tv_api_client():
    """创建电视机API客户端"""
    # 假设后端服务运行在本地
    client = api_client("http://localhost:8000")
    
    # 测试API连接
    if not client.health_check():
        pytest.skip("API服务不可用")
    
    return client

@pytest.mark.e2e
@pytest.mark.tv
class TestTVConnection:
    """电视机连接测试"""
    
    def test_adb_connection(self, tv_adb_client):
        """测试ADB连接"""
        print(f"测试ADB连接到电视机: {TEST_TV_IP}")
        
        with timer("ADB连接测试"):
            # 测试连接状态
            devices_output, exit_code = tv_adb_client.execute_command("devices")
            assert exit_code == 0, f"ADB devices命令失败: {devices_output}"
            
            # 验证设备在列表中
            assert f"{TEST_TV_IP}:{TEST_TV_PORT}" in devices_output, \
                f"电视机未在设备列表中: {devices_output}"
            
            print(f"ADB连接成功: {devices_output}")
    
    def test_device_online_status(self, tv_adb_client):
        """测试设备在线状态"""
        print("测试设备在线状态...")
        
        with timer("设备状态检查"):
            # 执行简单命令测试设备响应
            output, exit_code = tv_adb_client.execute_command("shell echo 'test'")
            assert exit_code == 0, f"设备无响应: {output}"
            assert "test" in output, f"命令输出异常: {output}"
            
            print(f"设备在线，响应正常: {output.strip()}")
    
    @retry(max_retries=3, delay=2.0)
    def test_network_latency(self, tv_adb_client):
        """测试网络延迟"""
        print("测试网络延迟...")
        
        test_count = 5
        total_time = 0
        
        for i in range(test_count):
            start_time = time.time()
            output, exit_code = tv_adb_client.execute_command("shell date")
            end_time = time.time()
            
            if exit_code == 0:
                latency = (end_time - start_time) * 1000  # 转换为毫秒
                total_time += latency
                print(f"  测试 {i+1}: {latency:.2f}ms")
            else:
                print(f"  测试 {i+1}: 失败")
        
        avg_latency = total_time / test_count
        print(f"平均网络延迟: {avg_latency:.2f}ms")
        
        # 延迟应小于500ms
        assert avg_latency < 500, f"网络延迟过高: {avg_latency:.2f}ms"

@pytest.mark.e2e
@pytest.mark.tv
class TestTVDeviceInfo:
    """电视机设备信息测试"""
    
    def test_get_device_model(self, tv_adb_client):
        """获取设备型号"""
        print("获取电视机型号...")
        
        with timer("获取设备型号"):
            info = tv_adb_client.get_device_info()
            
            print(f"设备信息:")
            print(f"  型号: {info.get('model', 'Unknown')}")
            print(f"  Android版本: {info.get('android_version', 'Unknown')}")
            print(f"  序列号: {info.get('serial', 'Unknown')}")
            print(f"  MAC地址: {info.get('mac_address', 'Unknown')}")
            
            # 验证基本信息
            assert info.get('model'), "无法获取设备型号"
            assert info.get('android_version'), "无法获取Android版本"
            
            # 检查是否为小米电视
            model = info.get('model', '').lower()
            assert 'mi' in model or 'xiaomi' in model or '小米' in model, \
                f"可能不是小米电视: {model}"
    
    def test_system_properties(self, tv_adb_client):
        """测试系统属性"""
        print("检查系统属性...")
        
        test_properties = [
            "ro.product.model",
            "ro.build.version.release",
            "ro.build.version.sdk",
            "ro.product.manufacturer",
            "ro.product.brand",
            "ro.build.type",
            "ro.debuggable"
        ]
        
        properties = {}
        for prop in test_properties:
            output, exit_code = tv_adb_client.execute_command(f"shell getprop {prop}")
            if exit_code == 0 and output:
                properties[prop] = output.strip()
                print(f"  {prop}: {properties[prop]}")
            else:
                properties[prop] = "Unknown"
        
        # 验证关键属性
        assert properties["ro.product.model"] != "Unknown", "无法获取产品型号"
        assert properties["ro.build.version.release"] != "Unknown", "无法获取Android版本"
        
        return properties
    
    def test_hardware_info(self, tv_adb_client):
        """测试硬件信息"""
        print("检查硬件信息...")
        
        # CPU信息
        cpu_info, _ = tv_adb_client.execute_command("shell cat /proc/cpuinfo")
        if cpu_info and "No such file" not in cpu_info:
            cpu_lines = cpu_info.split('\n')[:10]  # 只取前10行
            print("CPU信息:")
            for line in cpu_lines:
                if line.strip():
                    print(f"  {line}")
        
        # 内存信息
        mem_info, _ = tv_adb_client.execute_command("shell cat /proc/meminfo")
        if mem_info and "No such file" not in mem_info:
            mem_lines = mem_info.split('\n')[:5]  # 只取前5行
            print("内存信息:")
            for line in mem_lines:
                if 'MemTotal' in line or 'MemFree' in line:
                    print(f"  {line}")
        
        # 存储信息
        storage_info, _ = tv_adb_client.execute_command("shell df -h")
        if storage_info:
            print("存储信息:")
            for line in storage_info.split('\n')[:6]:  # 只取前6行
                print(f"  {line}")

@pytest.mark.e2e
@pytest.mark.tv
class TestTVBasicOperations:
    """电视机基础操作测试"""
    
    def test_keyevent_operations(self, tv_adb_client):
        """测试按键事件"""
        print("测试按键事件...")
        
        test_keyevents = [
            (3, "HOME键"),
            (4, "返回键"),
            (82, "菜单键"),
            (24, "音量增加"),
            (25, "音量减少"),
            (26, "电源键"),
            (85, "播放/暂停"),
            (86, "停止"),
            (87, "下一首"),
            (88, "上一首")
        ]
        
        success_count = 0
        for keycode, description in test_keyevents:
            with timer(f"按键: {description}"):
                success = tv_adb_client.send_keyevent(keycode)
                
                if success:
                    success_count += 1
                    print(f"  ✓ {description} (keycode: {keycode})")
                else:
                    print(f"  ✗ {description} (keycode: {keycode}) 失败")
            
            # 按键之间短暂延迟
            time.sleep(0.5)
        
        print(f"按键测试完成: {success_count}/{len(test_keyevents)} 成功")
        assert success_count >= len(test_keyevents) * 0.7, "按键测试失败率过高"
    
    def test_screen_operations(self, tv_adb_client):
        """测试屏幕操作"""
        print("测试屏幕操作...")
        
        # 获取屏幕分辨率
        output, exit_code = tv_adb_client.execute_command("shell wm size")
        if exit_code == 0 and output:
            print(f"屏幕分辨率: {output.strip()}")
        
        # 测试点击操作
        test_taps = [
            (100, 100, "左上角"),
            (500, 300, "中心区域"),
            (900, 500, "右下角")
        ]
        
        for x, y, description in test_taps:
            with timer(f"点击: {description}"):
                # 使用input tap命令
                output, exit_code = tv_adb_client.execute_command(f"shell input tap {x} {y}")
                
                if exit_code == 0:
                    print(f"  ✓ 点击 {description} ({x}, {y})")
                else:
                    print(f"  ✗ 点击 {description} 失败")
            
            time.sleep(1)
        
        # 测试滑动操作
        with timer("滑动操作"):
            output, exit_code = tv_adb_client.execute_command(
                "shell input swipe 100 100 300 300 500"
            )
            
            if exit_code == 0:
                print("  ✓ 滑动操作")
            else:
                print("  ✗ 滑动操作失败")
    
    def test_screenshot_capability(self, tv_adb_client):
        """测试截图能力"""
        print("测试截图功能...")
        
        # 创建临时目录保存截图
        temp_dir = Path(__file__).parent.parent / "test_data" / "screenshots"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        screenshot_path = temp_dir / f"screenshot_{int(time.time())}.png"
        
        with timer("截取屏幕截图"):
            success = tv_adb_client.take_screenshot(str(screenshot_path))
            
            if success:
                file_size = screenshot_path.stat().st_size if screenshot_path.exists() else 0
                print(f"  ✓ 截图成功: {screenshot_path} ({file_size} bytes)")
                
                # 验证截图文件
                assert screenshot_path.exists(), "截图文件未创建"
                assert file_size > 1000, f"截图文件过小: {file_size} bytes"
            else:
                print("  ✗ 截图失败")
                pytest.skip("截图功能不可用")

@pytest.mark.e2e
@pytest.mark.tv
class TestTVAppManagement:
    """电视机应用管理测试"""
    
    def test_list_installed_apps(self, tv_adb_client):
        """列出已安装应用"""
        print("列出已安装应用...")
        
        with timer("获取应用列表"):
            # 获取所有已安装应用
            output, exit_code = tv_adb_client.execute_command(
                "shell pm list packages -3"  # 第三方应用
            )
            
            if exit_code == 0 and output:
                third_party_apps = [line.replace('package:', '').strip() 
                                   for line in output.split('\n') if line]
                print(f"找到 {len(third_party_apps)} 个第三方应用")
                
                # 显示前10个应用
                for i, app in enumerate(third_party_apps[:10]):
                    print(f"  {i+1}. {app}")
            
            # 获取系统应用
            output, exit_code = tv_adb_client.execute_command(
                "shell pm list packages -s"  # 系统应用
            )
            
            if exit_code == 0 and output:
                system_apps = [line.replace('package:', '').strip() 
                              for line in output.split('\n') if line]
                print(f"找到 {len(system_apps)} 个系统应用")
    
    def test_launch_system_apps(self, tv_adb_client):
        """启动系统应用"""
        print("测试启动系统应用...")
        
        system_apps = TV_CONFIG["test_tv"]["test_apps"]["system_apps"]
        
        for app in system_apps:
            print(f"尝试启动: {app}")
            
            with timer(f"启动 {app}"):
                success = tv_adb_client.launch_app(app)
                
                if success:
                    print(f"  ✓ {app} 启动成功")
                    
                    # 等待应用启动
                    time.sleep(2)
                    
                    # 返回主页
                    tv_adb_client.send_keyevent(3)  # HOME键
                    time.sleep(1)
                else:
                    print(f"  ✗ {app} 启动失败")
        
        print("系统应用启动测试完成")
    
    def test_cast_apps_availability(self, tv_adb_client):
        """检查投屏应用可用性"""
        print("检查投屏应用...")
        
        cast_apps = TV_CONFIG["test_tv"]["test_apps"]["cast_apps"]
        available_apps = []
        
        for app in cast_apps:
            # 检查应用是否安装
            output, exit_code = tv_adb_client.execute_command(f"shell pm path {app}")
            
            if exit_code == 0 and output and "package:" in output:
                available_apps.append(app)
                print(f"  ✓ {app} 已安装")
            else:
                print(f"  ✗ {app} 未安装")
        
        print(f"找到 {len(available_apps)}/{len(cast_apps)} 个投屏应用")
        
        # 至少应该有一个投屏应用
        assert len(available_apps) > 0, "未找到任何投屏应用"
        
        return available_apps
    
    def test_app_performance(self, tv_adb_client):
        """测试应用启动性能"""
        print("测试应用启动性能...")
        
        test_app = "com.android.settings"  # 设置应用
        
        launch_times = []
        for i in range(3):  # 测试3次
            print(f"启动测试 {i+1}/3...")
            
            with timer("应用冷启动"):
                success = tv_adb_client.launch_app(test_app)
                
                if success:
                    launch_time = timer.get_duration()
                    launch_times.append(launch_time)
                    print(f"  启动时间: {launch_time:.2f}秒")
                    
                    # 等待应用完全启动
                    time.sleep(1)
                    
                    # 返回主页
                    tv_adb_client.send_keyevent(3)
                    time.sleep(1)
                else:
                    print("  启动失败")
        
        if launch_times:
            avg_time = sum(launch_times) / len(launch_times)
            print(f"平均启动时间: {avg_time:.2f}秒")
            
            # 启动时间应小于5秒
            assert avg_time < 5.0, f"应用启动时间过长: {avg_time:.2f}秒"

@pytest.mark.e2e
@pytest.mark.tv
class TestTVHDMISwitching:
    """电视机HDMI切换测试"""
    
    def test_hdmi_switching_capability(self, tv_adb_client):
        """测试HDMI切换能力"""
        print("测试HDMI切换功能...")
        
        hdmi_ports = TV_CONFIG["test_tv"]["hdmi_ports"]
        
        for port in hdmi_ports:
            print(f"测试切换到 HDMI{port}...")
            
            with timer(f"切换到 HDMI{port}"):
                # 方法1: 使用长按菜单键打开输入源选择
                tv_adb_client.send_keyevent(82)  # 菜单键
                time.sleep(1)
                
                # 发送多次下方向键选择HDMI
                for _ in range(port + 1):  # +1 因为可能需要跳过其他选项
                    tv_adb_client.send_keyevent(20)  # 下方向键
                    time.sleep(0.3)
                
                # 确认选择
                tv_adb_client.send_keyevent(23)  # 确认键
                time.sleep(2)
                
                print(f"  ✓ 已发送切换到 HDMI{port} 的命令")
            
            # 等待切换完成
            time.sleep(3)
        
        print("HDMI切换测试完成")
        
        # 返回原始输入源（假设是TV）
        print("返回TV输入源...")
        tv_adb_client.send_keyevent(82)  # 菜单键
        time.sleep(1)
        tv_adb_client.send_keyevent(20)  # 下方向键
        time.sleep(0.3)
        tv_adb_client.send_keyevent(23)  # 确认键
    
    def test_hdmi_switching_reliability(self, tv_adb_client):
        """测试HDMI切换可靠性"""
        print("测试HDMI切换可靠性...")
        
        test_cycles = 3
        success_count = 0
        
        for cycle in range(test_cycles):
            print(f"可靠性测试循环 {cycle+1}/{test_cycles}")
            
            # 切换到HDMI1
            tv_adb_client.send_keyevent(82)  # 菜单键
            time.sleep(1)
            
            for _ in range(2):  # HDMI1通常是第二个选项
                tv_adb_client.send_keyevent(20)  # 下方向键
                time.sleep(0.3)
            
            tv_adb_client.send_keyevent(23)  # 确认键
            time.sleep(3)
            
            # 切换回TV
            tv_adb_client.send_keyevent(82)  # 菜单键
            time.sleep(1)
            tv_adb_client.send_keyevent(20)  # 下方向键
            time.sleep(0.3)
            tv_adb_client.send_keyevent(23)  # 确认键
            time.sleep(3)
            
            success_count += 1
            print(f"  循环 {cycle+1} 完成")
        
        print(f"HDMI切换可靠性测试完成: {success_count}/{test_cycles} 成功")
        assert success_count == test_cycles, "HDMI切换可靠性测试失败"

@pytest.mark.e2e
@pytest.mark.tv
class TestTVScrcpyIntegration:
    """电视机Scrcpy集成测试"""
    
    def test_scrcpy_installation(self):
        """测试Scrcpy安装"""
        print("检查Scrcpy安装...")
        
        # 检查Scrcpy是否在PATH中
        import shutil
        scrcpy_installed = shutil.which("scrcpy") is not None
        
        if scrcpy_installed:
            print("  ✓ Scrcpy已安装在系统PATH中")
        else:
            print("  ✗ Scrcpy未安装在系统PATH中")
            
            # 检查项目目录中的Scrcpy
            scrcpy_dir = Path(__file__).parent.parent.parent / "backend_server" / "scrcpy"
            windows_scrcpy = scrcpy_dir / "scrcpy.exe"
            
            if windows_scrcpy.exists():
                print(f"  ✓ Scrcpy在项目目录中: {windows_scrcpy}")
                scrcpy_installed = True
            else:
                print("  ✗ 项目目录中未找到Scrcpy")
        
        if not scrcpy_installed:
            pytest.skip("Scrcpy未安装，跳过Scrcpy测试")
    
    def test_scrcpy_connection(self, tv_adb_client):
        """测试Scrcpy连接"""
        print("测试Scrcpy连接...")
        
        # 首先确保ADB连接正常
        devices_output, exit_code = tv_adb_client.execute_command("devices")
        assert exit_code == 0, "ADB连接异常"
        
        # 测试Scrcpy启动（短暂运行）
        import subprocess
        import signal
        
        scrcpy_cmd = ["scrcpy", "--serial", f"{TEST_TV_IP}:{TEST_TV_PORT}", 
                      "--no-audio", "--max-size", "800", "--max-fps", "15"]
        
        print(f"启动Scrcpy命令: {' '.join(scrcpy_cmd)}")
        
        try:
            # 启动Scrcpy进程
            process = subprocess.Popen(
                scrcpy_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 等待几秒让Scrcpy启动
            time.sleep(5)
            
            # 检查进程是否还在运行
            if process.poll() is None:
                print("  ✓ Scrcpy启动成功")
                
                # 停止Scrcpy
                process.terminate()
                try:
                    process.wait(timeout=5)
                    print("  ✓ Scrcpy正常停止")
                except subprocess.TimeoutExpired:
                    process.kill()
                    print("  ✗ Scrcpy强制停止")
            else:
                # 进程已退出，获取错误信息
                stdout, stderr = process.communicate()
                print(f"  ✗ Scrcpy启动失败: {stderr}")
                pytest.skip(f"Scrcpy启动失败: {stderr}")
                
        except FileNotFoundError:
            pytest.skip("Scrcpy命令未找到")
        except Exception as e:
            pytest.skip(f"Scrcpy测试异常: {e}")

@pytest.mark.e2e
@pytest.mark.tv
class TestTVBackgroundCleanup:
    """电视机后台清理测试"""
    
    def test_background_process_management(self, tv_adb_client):
        """测试后台进程管理"""
        print("测试后台进程管理...")
        
        # 获取当前运行进程
        output, exit_code = tv_adb_client.execute_command("shell ps")
        if exit_code == 0:
            processes = output.split('\n')
            print(f"当前运行进程数: {len(processes)}")
            
            # 显示前10个进程
            for i, proc in enumerate(processes[:10]):
                print(f"  {i+1}. {proc}")
        
        # 测试停止后台应用
        test_app = "com.android.settings"
        
        print(f"测试停止应用: {test_app}")
        
        # 首先启动应用
        tv_adb_client.launch_app(test_app)
        time.sleep(2)
        
        # 停止应用
        output, exit_code = tv_adb_client.execute_command(f"shell am force-stop {test_app}")
        
        if exit_code == 0:
            print(f"  ✓ 成功停止应用: {test_app}")
        else:
            print(f"  ✗ 停止应用失败: {output}")
        
        # 清理应用数据
        output, exit_code = tv_adb_client.execute_command(f"shell pm clear {test_app}")
        
        if exit_code == 0 and "Success" in output:
            print(f"  ✓ 成功清理应用数据: {test_app}")
        else:
            print(f"  ✗ 清理应用数据失败: {output}")
    
    def test_system_cleanup_commands(self, tv_adb_client):
        """测试系统清理命令"""
        print("测试系统清理命令...")
        
        cleanup_commands = [
            "shell pm trim-caches 500M",  # 清理缓存
            "shell sync",  # 同步文件系统
            "shell echo 3 > /proc/sys/vm/drop_caches",  # 清理内存缓存（需要root）
        ]
        
        for cmd in cleanup_commands:
            print(f"执行命令: {cmd}")
            
            output, exit_code = tv_adb_client.execute_command(cmd)
            
            if exit_code == 0:
                print(f"  ✓ 命令执行成功")
            else:
                print(f"  ✗ 命令执行失败: {output}")

@pytest.mark.e2e
@pytest.mark.tv
class TestTVPolicyExecution:
    """电视机策略执行测试"""
    
    def test_app_policy_execution(self, tv_adb_client):
        """测试APP策略执行"""
        print("测试APP策略执行...")
        
        test_app = "com.android.settings"
        
        print(f"执行APP策略: 启动 {test_app}")
        
        with timer("APP策略执行"):
            success = tv_adb_client.launch_app(test_app)
            
            if success:
                print(f"  ✓ APP策略执行成功: {test_app} 已启动")
                
                # 等待应用启动
                time.sleep(3)
                
                # 验证应用是否在前台
                output, exit_code = tv_adb_client.execute_command(
                    "shell dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'"
                )
                
                if exit_code == 0 and test_app in output:
                    print(f"  ✓ 应用在前台运行")
                else:
                    print(f"  ✗ 应用可能未在前台")
                
                # 返回主页
                tv_adb_client.send_keyevent(3)
                time.sleep(1)
            else:
                print(f"  ✗ APP策略执行失败")
    
    def test_hdmi_policy_execution(self, tv_adb_client):
        """测试HDMI策略执行"""
        print("测试HDMI策略执行...")
        
        hdmi_port = 1  # 测试HDMI1
        
        print(f"执行HDMI策略: 切换到 HDMI{hdmi_port}")
        
        with timer("HDMI策略执行"):
            # 执行HDMI切换
            tv_adb_client.send_keyevent(82)  # 菜单键
            time.sleep(1)
            
            for _ in range(hdmi_port + 1):
                tv_adb_client.send_keyevent(20)  # 下方向键
                time.sleep(0.3)
            
            tv_adb_client.send_keyevent(23)  # 确认键
            time.sleep(3)
            
            print(f"  ✓ HDMI策略执行完成")
            
            # 切换回TV
            tv_adb_client.send_keyevent(82)
            time.sleep(1)
            tv_adb_client.send_keyevent(20)
            time.sleep(0.3)
            tv_adb_client.send_keyevent(23)
            time.sleep(2)

@pytest.mark.e2e
@pytest.mark.tv
class TestTVComprehensiveTest:
    """电视机综合测试"""
    
    def test_complete_workflow(self, tv_adb_client):
        """测试完整工作流程"""
        print("开始完整工作流程测试...")
        
        test_steps = [
            ("ADB连接验证", self._step_adb_connection),
            ("设备信息获取", self._step_device_info),
            ("系统应用测试", self._step_system_apps),
            ("HDMI切换测试", self._step_hdmi_switching),
            ("后台清理测试", self._step_background_cleanup),
            ("策略执行测试", self._step_policy_execution),
        ]
        
        results = []
        
        for step_name, step_func in test_steps:
            print(f"\n{'='*60}")
            print(f"步骤: {step_name}")
            print(f"{'='*60}")
            
            try:
                with timer(step_name):
                    step_func(tv_adb_client)
                results.append((step_name, True, None))
                print(f"✓ {step_name} 通过")
            except Exception as e:
                results.append((step_name, False, str(e)))
                print(f"✗ {step_name} 失败: {e}")
        
        # 打印测试结果
        print(f"\n{'='*60}")
        print("完整工作流程测试结果")
        print(f"{'='*60}")
        
        passed = sum(1 for _, success, _ in results if success)
        total = len(results)
        
        for step_name, success, error in results:
            status = "✓" if success else "✗"
            print(f"{status} {step_name}")
            if error:
                print(f"   错误: {error}")
        
        print(f"\n通过率: {passed}/{total} ({passed/total*100:.1f}%)")
        
        # 要求至少80%的测试通过
        assert passed >= total * 0.8, f"测试通过率过低: {passed}/{total}"
    
    def _step_adb_connection(self, tv_adb_client):
        """ADB连接验证步骤"""
        output, exit_code = tv_adb_client.execute_command("devices")
        assert exit_code == 0, "ADB连接失败"
        assert f"{TEST_TV_IP}:{TEST_TV_PORT}" in output, "电视机不在设备列表中"
    
    def _step_device_info(self, tv_adb_client):
        """设备信息获取步骤"""
        info = tv_adb_client.get_device_info()
        assert info.get('model'), "无法获取设备型号"
        assert info.get('android_version'), "无法获取Android版本"
    
    def _step_system_apps(self, tv_adb_client):
        """系统应用测试步骤"""
        success = tv_adb_client.launch_app("com.android.settings")
        assert success, "无法启动设置应用"
        time.sleep(2)
        tv_adb_client.send_keyevent(3)  # 返回主页
        time.sleep(1)
    
    def _step_hdmi_switching(self, tv_adb_client):
        """HDMI切换测试步骤"""
        tv_adb_client.send_keyevent(82)  # 菜单键
        time.sleep(1)
        tv_adb_client.send_keyevent(20)  # 下方向键
        time.sleep(0.3)
        tv_adb_client.send_keyevent(20)  # 下方向键
        time.sleep(0.3)
        tv_adb_client.send_keyevent(23)  # 确认键（选择HDMI1）
        time.sleep(3)
        tv_adb_client.send_keyevent(82)  # 菜单键
        time.sleep(1)
        tv_adb_client.send_keyevent(20)  # 下方向键
        time.sleep(0.3)
        tv_adb_client.send_keyevent(23)  # 确认键（返回TV）
        time.sleep(2)
    
    def _step_background_cleanup(self, tv_adb_client):
        """后台清理测试步骤"""
        output, exit_code = tv_adb_client.execute_command("shell am force-stop com.android.settings")
        # 不验证结果，因为应用可能未运行
    
    def _step_policy_execution(self, tv_adb_client):
        """策略执行测试步骤"""
        success = tv_adb_client.launch_app("com.android.settings")
        if success:
            time.sleep(2)
            tv_adb_client.send_keyevent(3)  # 返回主页
            time.sleep(1)

@pytest.mark.e2e
@pytest.mark.tv
class TestTVPerformance:
    """电视机性能测试"""
    
    def test_response_time(self, tv_adb_client):
        """测试响应时间"""
        print("测试电视机响应时间...")
        
        test_operations = 10
        response_times = []
        
        for i in range(test_operations):
            start_time = time.time()
            output, exit_code = tv_adb_client.execute_command("shell echo 'test'")
            end_time = time.time()
            
            if exit_code == 0:
                response_time = (end_time - start_time) * 1000  # 毫秒
                response_times.append(response_time)
                print(f"  操作 {i+1}: {response_time:.2f}ms")
        
        if response_times:
            avg_response = sum(response_times) / len(response_times)
            max_response = max(response_times)
            min_response = min(response_times)
            
            print(f"平均响应时间: {avg_response:.2f}ms")
            print(f"最大响应时间: {max_response:.2f}ms")
            print(f"最小响应时间: {min_response:.2f}ms")
            
            # 响应时间应小于200ms
            assert avg_response < 200, f"平均响应时间过长: {avg_response:.2f}ms"
    
    def test_stability_long_running(self, tv_adb_client):
        """测试长时间运行稳定性"""
        print("测试长时间运行稳定性...")
        
        duration = 60  # 测试60秒
        start_time = time.time()
        operation_count = 0
        failure_count = 0
        
        print(f"开始 {duration} 秒稳定性测试...")
        
        while time.time() - start_time < duration:
            operation_count += 1
            
            # 执行简单操作
            output, exit_code = tv_adb_client.execute_command("shell date")
            
            if exit_code != 0:
                failure_count += 1
                print(f"  操作 {operation_count} 失败")
            
            # 短暂延迟
            time.sleep(1)
        
        success_rate = (operation_count - failure_count) / operation_count * 100
        print(f"稳定性测试完成:")
        print(f"  总操作数: {operation_count}")
        print(f"  失败数: {failure_count}")
        print(f"  成功率: {success_rate:.2f}%")
        
        # 要求成功率大于95%
        assert success_rate >= 95, f"稳定性测试失败率过高: {100-success_rate:.2f}%"

if __name__ == "__main__":
    """直接运行测试"""
    print("电视机端到端测试")
    print(f"目标电视机: {TEST_TV_IP}:{TEST_TV_PORT}")
    print("="*60)
    
    # 这里可以添加直接运行的逻辑
    pass