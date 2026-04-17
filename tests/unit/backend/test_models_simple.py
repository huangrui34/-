"""
简化的数据库模型单元测试
"""
import pytest
from datetime import datetime

@pytest.mark.unit
class TestDeviceModel:
    """设备模型测试"""
    
    def test_device_creation(self, db_session):
        """测试设备创建"""
        from backend_server.app.models import Device
        
        # 创建设备
        device = Device(
            device_sn="TEST-SN-001",
            device_name="测试电视机",
            token="test_token_123",
            room_name="101",
            wifi_mac="00:11:22:33:44:55",
            eth_mac="AA:BB:CC:DD:EE:FF",
            wifi_ip="192.168.1.100",
            eth_ip="192.168.1.101"
        )
        
        db_session.add(device)
        db_session.commit()
        
        # 验证数据
        assert device.id is not None
        assert device.device_sn == "TEST-SN-001"
        assert device.device_name == "测试电视机"
        assert device.token == "test_token_123"
        assert device.room_name == "101"
        assert device.wifi_mac == "00:11:22:33:44:55"
        assert device.eth_mac == "AA:BB:CC:DD:EE:FF"
        assert device.wifi_ip == "192.168.1.100"
        assert device.eth_ip == "192.168.1.101"
        assert device.online is False  # 默认值
        assert device.updated_at is not None
        assert isinstance(device.updated_at, datetime)
    
    def test_device_unique_sn(self, db_session):
        """测试设备序列号唯一性约束"""
        from backend_server.app.models import Device
        from sqlalchemy.exc import IntegrityError
        
        # 创建第一个设备
        device1 = Device(
            device_sn="UNIQUE-SN-001",
            device_name="TV1",
            token="token1"
        )
        db_session.add(device1)
        db_session.commit()
        
        # 尝试创建具有相同序列号的第二个设备
        device2 = Device(
            device_sn="UNIQUE-SN-001",  # 相同的序列号
            device_name="TV2",
            token="token2"
        )
        db_session.add(device2)
        
        # 应该抛出完整性错误
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
    
    def test_device_update(self, db_session, test_device):
        """测试设备更新"""
        # 更新设备信息
        test_device.device_name = "更新后的电视机"
        test_device.room_name = "202"
        test_device.online = True
        
        db_session.commit()
        db_session.refresh(test_device)
        
        # 验证更新
        assert test_device.device_name == "更新后的电视机"
        assert test_device.room_name == "202"
        assert test_device.online is True
    
    def test_device_delete(self, db_session, test_device):
        """测试设备删除"""
        device_id = test_device.id
        
        # 删除设备
        db_session.delete(test_device)
        db_session.commit()
        
        # 验证设备已被删除
        from backend_server.app.models import Device
        deleted_device = db_session.query(Device).filter(Device.id == device_id).first()
        assert deleted_device is None

@pytest.mark.unit
class TestPolicyModel:
    """策略模型测试"""
    
    def test_policy_creation(self, db_session):
        """测试策略创建"""
        from backend_server.app.models import Policy
        
        # 创建应用模式策略
        app_policy = Policy(
            name="应用启动策略",
            mode="app",
            target_app_package="com.example.app"
        )
        db_session.add(app_policy)
        db_session.commit()
        
        assert app_policy.id is not None
        assert app_policy.name == "应用启动策略"
        assert app_policy.mode == "app"
        assert app_policy.target_app_package == "com.example.app"
        assert app_policy.target_hdmi_port is None
        assert app_policy.is_active is True  # 默认值
        
        # 创建HDMI模式策略
        hdmi_policy = Policy(
            name="HDMI切换策略",
            mode="hdmi",
            target_hdmi_port=2
        )
        db_session.add(hdmi_policy)
        db_session.commit()
        
        assert hdmi_policy.id is not None
        assert hdmi_policy.name == "HDMI切换策略"
        assert hdmi_policy.mode == "hdmi"
        assert hdmi_policy.target_hdmi_port == 2
        assert hdmi_policy.target_app_package is None
    
    def test_policy_unique_name(self, db_session):
        """测试策略名称唯一性"""
        from backend_server.app.models import Policy
        from sqlalchemy.exc import IntegrityError
        
        # 创建第一个策略
        policy1 = Policy(
            name="唯一策略",
            mode="app",
            target_app_package="com.test.app"
        )
        db_session.add(policy1)
        db_session.commit()
        
        # 尝试创建具有相同名称的第二个策略
        policy2 = Policy(
            name="唯一策略",  # 相同的名称
            mode="hdmi",
            target_hdmi_port=1
        )
        db_session.add(policy2)
        
        # 应该抛出完整性错误
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
    
    def test_policy_update(self, db_session):
        """测试策略更新"""
        from backend_server.app.models import Policy
        
        # 创建策略
        policy = Policy(
            name="测试策略",
            mode="app",
            target_app_package="com.old.app"
        )
        db_session.add(policy)
        db_session.commit()
        
        # 更新策略
        policy.mode = "hdmi"
        policy.target_app_package = None
        policy.target_hdmi_port = 3
        policy.is_active = False
        
        db_session.commit()
        db_session.refresh(policy)
        
        assert policy.mode == "hdmi"
        assert policy.target_app_package is None
        assert policy.target_hdmi_port == 3
        assert policy.is_active is False
        
        db_session.delete(policy)
        db_session.commit()

@pytest.mark.unit
class TestDevicePolicyRelationship:
    """设备-策略关系测试"""
    
    def test_device_policy_association(self, db_session):
        """测试设备与策略关联"""
        from backend_server.app.models import Device, Policy
        
        # 创建策略
        policy = Policy(
            name="关联测试策略",
            mode="app",
            target_app_package="com.relation.test"
        )
        db_session.add(policy)
        db_session.commit()
        
        # 创建设备并关联策略
        device = Device(
            device_sn="REL-SN-001",
            device_name="关联测试设备",
            token="rel_token_123",
            policy_id=policy.id
        )
        db_session.add(device)
        db_session.commit()
        
        # 验证关联
        assert device.policy_id == policy.id
        assert device.policy.id == policy.id
        assert device.policy.name == "关联测试策略"
        
        # 清理
        db_session.delete(device)
        db_session.delete(policy)
        db_session.commit()

@pytest.mark.unit
class TestOperationLogModel:
    """操作日志模型测试"""
    
    def test_operation_log_creation(self, db_session, test_device):
        """测试操作日志创建"""
        from backend_server.app.models import OperationLog
        
        # 创建操作日志
        log = OperationLog(
            device_id=test_device.id,
            device_name=test_device.device_name,
            action="install",
            detail="测试安装应用",
            operator="admin"
        )
        db_session.add(log)
        db_session.commit()
        
        assert log.id is not None
        assert log.device_id == test_device.id
        assert log.device_name == test_device.device_name
        assert log.action == "install"
        assert log.detail == "测试安装应用"
        assert log.operator == "admin"
        assert log.created_at is not None
        assert isinstance(log.created_at, datetime)
    
    def test_operation_log_types(self, db_session, test_device):
        """测试操作日志类型"""
        from backend_server.app.models import OperationLog
        
        # 测试不同的操作类型
        actions = ["install", "uninstall", "start", "stop", "screenshot", 
                  "remote_control", "policy_update", "device_register"]
        
        for action in actions:
            log = OperationLog(
                device_id=test_device.id,
                device_name=test_device.device_name,
                action=action,
                detail=f"测试{action}操作",
                operator="admin"
            )
            db_session.add(log)
            db_session.commit()
            
            assert log.action == action
            
            db_session.delete(log)
            db_session.commit()

@pytest.mark.unit
class TestDeviceHeartbeatModel:
    """设备心跳模型测试"""
    
    def test_heartbeat_creation(self, db_session, test_device):
        """测试心跳记录创建"""
        from backend_server.app.models import DeviceHeartbeat
        
        # 创建心跳记录
        heartbeat = DeviceHeartbeat(
            device_id=test_device.id,
            status="ok",
            message="设备运行正常"
        )
        db_session.add(heartbeat)
        db_session.commit()
        
        assert heartbeat.id is not None
        assert heartbeat.device_id == test_device.id
        assert heartbeat.status == "ok"
        assert heartbeat.message == "设备运行正常"
        assert heartbeat.created_at is not None
        assert isinstance(heartbeat.created_at, datetime)