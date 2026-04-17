"""
测试工具模块
提供测试辅助函数和工具
"""
import os
import sys
import time
import json
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

class TestTimer:
    """测试计时器"""
    
    def __init__(self, name: str = ""):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.duration = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
    
    def get_duration(self) -> float:
        """获取持续时间"""
        if self.duration is None:
            return time.time() - self.start_time
        return self.duration

class TestRetry:
    """测试重试装饰器"""
    
    def __init__(self, max_retries: int = 3, delay: float = 1.0, 
                 exceptions: tuple = (Exception,)):
        self.max_retries = max_retries
        self.delay = delay
        self.exceptions = exceptions
    
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(self.max_retries):
                try:
                    return func(*args, **kwargs)
                except self.exceptions as e:
                    last_exception = e
                    if attempt < self.max_retries - 1:
                        time.sleep(self.delay * (2 ** attempt))  # 指数退避
                    continue
            raise last_exception
        return wrapper

class ADBTestClient:
    """ADB测试客户端"""
    
    def __init__(self, ip: str, port: int = 5555):
        self.ip = ip
        self.port = port
        self.adb_path = self._find_adb()
    
    def _find_adb(self) -> str:
        """查找ADB路径"""
        # 检查常见位置
        possible_paths = [
            "adb",
            "platform-tools/adb",
            "C:\\Android\\platform-tools\\adb.exe",
            "C:\\Program Files\\Android\\platform-tools\\adb.exe",
            str(PROJECT_ROOT / "backend_server" / "adb" / "adb.exe"),
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, "--version"], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    return path
            except:
                continue
        
        raise FileNotFoundError("ADB not found")
    
    @TestRetry(max_retries=3, delay=2.0)
    def connect(self) -> bool:
        """连接到设备"""
        cmd = [self.adb_path, "connect", f"{self.ip}:{self.port}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if "connected to" in result.stdout or "already connected" in result.stdout:
            return True
        return False
    
    @TestRetry(max_retries=2, delay=1.0)
    def disconnect(self) -> bool:
        """断开连接"""
        cmd = [self.adb_path, "disconnect", f"{self.ip}:{self.port}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    
    def execute_command(self, command: str, timeout: int = 30) -> Tuple[str, int]:
        """执行ADB命令"""
        full_cmd = [self.adb_path, "-s", f"{self.ip}:{self.port}"] + command.split()
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip(), result.returncode
    
    def get_device_info(self) -> Dict[str, str]:
        """获取设备信息"""
        info = {}
        
        # 获取设备型号
        model, _ = self.execute_command("shell getprop ro.product.model")
        info["model"] = model.strip() if model else "Unknown"
        
        # 获取Android版本
        version, _ = self.execute_command("shell getprop ro.build.version.release")
        info["android_version"] = version.strip() if version else "Unknown"
        
        # 获取序列号
        serial, _ = self.execute_command("shell getprop ro.serialno")
        info["serial"] = serial.strip() if serial else "Unknown"
        
        # 获取MAC地址
        mac, _ = self.execute_command("shell cat /sys/class/net/wlan0/address")
        if not mac or "No such file" in mac:
            mac, _ = self.execute_command("shell ip link show wlan0")
            # 从ip命令输出中提取MAC地址
            for line in mac.split('\n'):
                if 'link/ether' in line:
                    mac = line.split()[1]
                    break
        
        info["mac_address"] = mac.strip() if mac and "No such file" not in mac else "Unknown"
        
        return info
    
    def install_apk(self, apk_path: str) -> bool:
        """安装APK"""
        if not os.path.exists(apk_path):
            raise FileNotFoundError(f"APK not found: {apk_path}")
        
        output, exit_code = self.execute_command(f"install -r {apk_path}", timeout=60)
        return "Success" in output and exit_code == 0
    
    def launch_app(self, package_name: str) -> bool:
        """启动应用"""
        output, exit_code = self.execute_command(
            f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        )
        return exit_code == 0
    
    def send_keyevent(self, keycode: int) -> bool:
        """发送按键事件"""
        output, exit_code = self.execute_command(f"shell input keyevent {keycode}")
        return exit_code == 0
    
    def take_screenshot(self, output_path: str) -> bool:
        """截取屏幕截图"""
        temp_file = "/sdcard/screenshot.png"
        
        # 截屏
        output, exit_code = self.execute_command(f"shell screencap -p {temp_file}")
        if exit_code != 0:
            return False
        
        # 拉取文件
        output, exit_code = self.execute_command(f"pull {temp_file} {output_path}")
        
        # 清理临时文件
        self.execute_command(f"shell rm {temp_file}")
        
        return exit_code == 0 and os.path.exists(output_path)

class APITestClient:
    """API测试客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = self._create_session()
        self.token = None
    
    def _create_session(self) -> requests.Session:
        """创建HTTP会话"""
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def set_token(self, token: str):
        """设置认证令牌"""
        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        
        # 添加超时
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 30
        
        try:
            response = self.session.request(method, url, **kwargs)
            return response
        except requests.exceptions.RequestException as e:
            raise Exception(f"API请求失败: {e}")
    
    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """发送GET请求"""
        return self.request("GET", endpoint, **kwargs)
    
    def post(self, endpoint: str, **kwargs) -> requests.Response:
        """发送POST请求"""
        return self.request("POST", endpoint, **kwargs)
    
    def put(self, endpoint: str, **kwargs) -> requests.Response:
        """发送PUT请求"""
        return self.request("PUT", endpoint, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """发送DELETE请求"""
        return self.request("DELETE", endpoint, **kwargs)
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            response = self.get("/health")
            return response.status_code == 200
        except:
            return False
    
    def register_device(self, device_data: Dict[str, Any]) -> Dict[str, Any]:
        """注册设备"""
        response = self.post("/api/v1/devices/register", json=device_data)
        response.raise_for_status()
        return response.json()
    
    def get_devices(self) -> List[Dict[str, Any]]:
        """获取设备列表"""
        response = self.get("/api/v1/devices")
        response.raise_for_status()
        return response.json()
    
    def update_policy(self, device_id: int, policy_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新策略"""
        response = self.put(f"/api/v1/devices/{device_id}/policy", json=policy_data)
        response.raise_for_status()
        return response.json()
    
    def remote_control(self, device_id: int, command: str) -> Dict[str, Any]:
        """远程控制"""
        response = self.post(f"/api/v1/devices/{device_id}/control", json={"command": command})
        response.raise_for_status()
        return response.json()

class TestDataGenerator:
    """测试数据生成器"""
    
    @staticmethod
    def generate_device_data(**overrides) -> Dict[str, Any]:
        """生成设备测试数据"""
        import random
        import string
        
        base_data = {
            "device_name": f"TestTV_{random.randint(1000, 9999)}",
            "mac_address": f"{random.randint(0, 255):02x}:{random.randint(0, 255):02x}:"
                          f"{random.randint(0, 255):02x}:{random.randint(0, 255):02x}:"
                          f"{random.randint(0, 255):02x}:{random.randint(0, 255):02x}",
            "ip_address": f"192.168.{random.randint(1, 254)}.{random.randint(2, 254)}",
            "room_number": f"Room{random.randint(100, 999)}",
            "location": random.choice(["会议室A", "会议室B", "会议室C", "大厅", "办公室"]),
            "status": random.choice(["online", "offline", "unknown"])
        }
        
        base_data.update(overrides)
        return base_data
    
    @staticmethod
    def generate_policy_data(**overrides) -> Dict[str, Any]:
        """生成策略测试数据"""
        import random
        
        modes = ["app", "hdmi"]
        apps = ["com.android.settings", "com.android.chrome", "com.example.cast"]
        
        base_data = {
            "mode": random.choice(modes),
            "target_app_package": random.choice(apps) if random.choice(modes) == "app" else None,
            "target_hdmi_port": random.randint(1, 3) if random.choice(modes) == "hdmi" else None
        }
        
        base_data.update(overrides)
        return base_data
    
    @staticmethod
    def generate_operation_data(**overrides) -> Dict[str, Any]:
        """生成操作测试数据"""
        import random
        
        operations = ["install_app", "update_policy", "remote_control", "take_screenshot", "reboot"]
        
        base_data = {
            "operation_type": random.choice(operations),
            "details": json.dumps({"test": True, "timestamp": time.time()}),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        base_data.update(overrides)
        return base_data

class TestAssertions:
    """测试断言工具"""
    
    @staticmethod
    def assert_response_success(response: requests.Response, 
                               expected_status: int = 200):
        """断言响应成功"""
        assert response.status_code == expected_status, \
            f"Expected status {expected_status}, got {response.status_code}"
        
        # 检查响应内容
        if response.headers.get('Content-Type', '').startswith('application/json'):
            data = response.json()
            assert "ok" in data or "success" in data or "status" in data, \
                "Response should contain success indicator"
    
    @staticmethod
    def assert_device_data(device_data: Dict[str, Any], 
                          expected_fields: List[str] = None):
        """断言设备数据完整性"""
        required_fields = ["id", "device_name", "mac_address", "ip_address", 
                          "created_at", "status"]
        
        if expected_fields:
            required_fields = expected_fields
        
        for field in required_fields:
            assert field in device_data, f"Missing required field: {field}"
            assert device_data[field] is not None, f"Field {field} should not be None"
    
    @staticmethod
    def assert_policy_data(policy_data: Dict[str, Any]):
        """断言策略数据有效性"""
        assert "mode" in policy_data, "Missing mode field"
        assert policy_data["mode"] in ["app", "hdmi"], f"Invalid mode: {policy_data['mode']}"
        
        if policy_data["mode"] == "app":
            assert "target_app_package" in policy_data, "Missing target_app_package for app mode"
            assert policy_data["target_app_package"], "target_app_package should not be empty"
        elif policy_data["mode"] == "hdmi":
            assert "target_hdmi_port" in policy_data, "Missing target_hdmi_port for hdmi mode"
            assert isinstance(policy_data["target_hdmi_port"], int), "target_hdmi_port should be integer"
            assert 1 <= policy_data["target_hdmi_port"] <= 3, "target_hdmi_port should be 1-3"
    
    @staticmethod
    def assert_performance(operation_name: str, duration: float, 
                          max_duration: float):
        """断言性能要求"""
        assert duration <= max_duration, \
            f"{operation_name} took {duration:.2f}s, exceeds max {max_duration}s"

# 导出常用工具
timer = TestTimer
retry = TestRetry
adb_client = ADBTestClient
api_client = APITestClient
data_gen = TestDataGenerator
assertions = TestAssertions