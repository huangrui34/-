"""
测试框架配置文件
提供测试所需的共享fixtures和配置
"""
import os
import sys
import pytest
import tempfile
import sqlite3
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend_server" / "app"))

# 测试配置
TEST_CONFIG = {
    "database_url": "sqlite:///:memory:",
    "test_tv_ip": "10.181.184.226",  # 测试电视机IP
    "test_tv_port": 5555,
    "api_base_url": "http://localhost:8000",
    "test_timeout": 30,  # 秒
    "max_retries": 3,
}

@pytest.fixture(scope="session")
def test_config():
    """返回测试配置"""
    return TEST_CONFIG.copy()

@pytest.fixture(scope="session")
def temp_db():
    """创建临时数据库"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")
    
    # 创建数据库连接
    conn = sqlite3.connect(db_path)
    
    # 创建测试表结构 - 匹配实际模型
    conn.execute("""
    CREATE TABLE IF NOT EXISTS policies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        mode TEXT NOT NULL,
        target_app_package TEXT,
        target_hdmi_port INTEGER,
        fallback_mode TEXT,
        fallback_value TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_sn TEXT UNIQUE NOT NULL,
        device_name TEXT NOT NULL,
        room_name TEXT,
        model_name TEXT,
        ip_address TEXT,
        wifi_ip TEXT,
        eth_ip TEXT,
        wifi_mac TEXT,
        eth_mac TEXT,
        network_ssid TEXT,
        installed_apps TEXT,
        ram_usage TEXT,
        storage_usage TEXT,
        online BOOLEAN DEFAULT 0,
        token TEXT UNIQUE NOT NULL,
        policy_id INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (policy_id) REFERENCES policies (id)
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS device_heartbeats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        status TEXT DEFAULT 'ok',
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (device_id) REFERENCES devices (id)
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS operation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        device_name TEXT,
        action TEXT NOT NULL,
        detail TEXT,
        operator TEXT DEFAULT 'admin',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    yield db_path
    conn.close()
    
    # 清理临时文件
    try:
        os.remove(db_path)
        os.rmdir(temp_dir)
    except:
        pass

@pytest.fixture(scope="function")
def db_session(temp_db):
    """创建数据库会话"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(f"sqlite:///{temp_db}")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()

@pytest.fixture(scope="function")
def test_device(db_session):
    """创建测试设备"""
    from backend_server.app.models import Device
    import uuid
    
    # 生成唯一的token
    unique_token = f"test_token_{uuid.uuid4().hex[:8]}"
    unique_sn = f"TEST-SN-{uuid.uuid4().hex[:8]}"
    
    device = Device(
        device_sn=unique_sn,
        device_name="测试电视机",
        token=unique_token,
        room_name="101",
        wifi_mac="00:11:22:33:44:55",
        eth_mac="AA:BB:CC:DD:EE:FF",
        wifi_ip="192.168.1.100",
        eth_ip="192.168.1.101"
    )
    
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    
    yield device
    
    # 清理 - 检查设备是否仍然存在
    try:
        db_session.delete(device)
        db_session.commit()
    except:
        db_session.rollback()

@pytest.fixture(scope="function")
def test_policy(db_session, test_device):
    """创建测试策略"""
    from backend_server.app.models import Policy
    
    policy = Policy(
        device_id=test_device.id,
        mode="app",
        target_app_package="com.android.settings"
    )
    
    db_session.add(policy)
    db_session.commit()
    db_session.refresh(policy)
    
    yield policy
    
    # 清理
    db_session.delete(policy)
    db_session.commit()

@pytest.fixture(scope="session")
def mock_adb():
    """模拟ADB命令执行"""
    class MockADB:
        def __init__(self):
            self.commands = []
            self.responses = {}
            
        def set_response(self, command, response, exit_code=0):
            """设置命令响应"""
            self.responses[command] = (response, exit_code)
            
        def execute(self, command):
            """执行模拟命令"""
            self.commands.append(command)
            
            # 检查是否有预设响应
            for cmd_pattern, (response, exit_code) in self.responses.items():
                if cmd_pattern in command:
                    return response, exit_code
            
            # 默认响应
            if "connect" in command:
                return "connected to", 0
            elif "devices" in command:
                return "List of devices attached\n192.168.1.100:5555\tdevice", 0
            elif "shell getprop" in command:
                if "ro.product.model" in command:
                    return "Mi TV 4A", 0
                elif "ro.build.version.release" in command:
                    return "9", 0
            elif "install" in command:
                return "Success", 0
            elif "shell input keyevent" in command:
                return "", 0
            
            return "", 0
    
    mock = MockADB()
    yield mock

@pytest.fixture(scope="session")
def test_client():
    """创建测试HTTP客户端"""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
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
    
    yield session
    
    session.close()

@pytest.fixture(scope="session")
def test_logger():
    """创建测试日志记录器"""
    import logging
    
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建文件处理器
    log_file = project_root / "tests" / "test_results.log"
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(logging.DEBUG)
    
    # 设置格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    yield logger
    
    # 清理处理器
    logger.removeHandler(console_handler)
    logger.removeHandler(file_handler)

# 测试标记定义
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers",
        "unit: 单元测试"
    )
    config.addinivalue_line(
        "markers",
        "integration: 集成测试"
    )
    config.addinivalue_line(
        "markers",
        "e2e: 端到端测试"
    )
    config.addinivalue_line(
        "markers",
        "performance: 性能测试"
    )
    config.addinivalue_line(
        "markers",
        "slow: 慢速测试（需要较长时间）"
    )
    config.addinivalue_line(
        "markers",
        "network: 需要网络连接的测试"
    )
    config.addinivalue_line(
        "markers",
        "adb: 需要ADB连接的测试"
    )
    config.addinivalue_line(
        "markers",
        "tv: 需要电视机的测试"
    )

# 测试收集钩子
def pytest_collection_modifyitems(config, items):
    """修改测试收集"""
    # 根据标记重新排序测试
    unit_tests = []
    integration_tests = []
    e2e_tests = []
    performance_tests = []
    other_tests = []
    
    for item in items:
        if item.get_closest_marker("unit"):
            unit_tests.append(item)
        elif item.get_closest_marker("integration"):
            integration_tests.append(item)
        elif item.get_closest_marker("e2e"):
            e2e_tests.append(item)
        elif item.get_closest_marker("performance"):
            performance_tests.append(item)
        else:
            other_tests.append(item)
    
    # 重新排序：单元测试 -> 集成测试 -> 端到端测试 -> 性能测试 -> 其他测试
    items[:] = unit_tests + integration_tests + e2e_tests + performance_tests + other_tests