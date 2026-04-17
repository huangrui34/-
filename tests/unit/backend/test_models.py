"""
数据库模型单元测试
"""
import pytest
from datetime import datetime
from test_utils import data_gen, assertions

@pytest.mark.unit
class TestDeviceModel:
    """设备模型测试"""
    
    def test_device_creation(self, db_session):
        """测试设备创建"""
        from backend_server.app.models import Device
        
        # 生成测试数据
        device_data = data_gen.generate_device_data()
        
        # 创建设备
        device = Device(**device_data)
        db_session.add(device)
        db_session.commit()
        
        # 验证数据
        assert device.id is not None
        assert device.device_name == device_data["device_name"]
        assert device.mac_address == device_data["mac_address"]
        assert device.ip_address == device_data["ip_address"]
        assert device.room_number == device_data["room_number"]
        assert device.location == device_data["location"]
        assert device.status == device_data["status"]
        assert device.created_at is not None
        assert isinstance(device.created_at, datetime)
        
        # 验证默认值
        assert device.token is None
        assert device.last_seen is None
    
    def test_device_unique_mac(self, db_session):
        """测试MAC地址唯一性约束"""
        from backend_server.app.models import Device
        from sqlalchemy.exc import IntegrityError
        
        # 创建第一个设备
        device1 = Device(
            device_name="TV1",
            mac_address="00:11:22:33:44:55",
            ip_address="192.168.1.100"
        )
        db_session.add(device1)
        db_session.commit()
        
        # 尝试创建具有相同MAC地址的第二个设备
        device2 = Device(
            device_name="TV2",
            mac_address="00:11:22:33:44:55",  # 相同的MAC地址
            ip_address="192.168.1.101"
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
        test_device.room_number = "202"
        test_device.location = "会议室B"
        test_device.status = "offline"
        
        db_session.commit()
        db_session.refresh(test_device)
        
        # 验证更新
        assert test_device.device_name == "更新后的电视机"
        assert test_device.room_number == "202"
        assert test_device.location == "会议室B"
        assert test_device.status == "offline"
    
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
    
    def test_device_relationships(self, db_session, test_device, test_policy):
        """测试设备关系"""
        # 验证设备与策略的关系
        assert len(test_device.policies) == 1
        assert test_device.policies[0].id == test_policy.id
        
        # 验证策略与设备的关系
        assert test_policy.device.id == test_device.id
        assert test_policy.device.device_name == test_device.device_name

@pytest.mark.unit
class TestPolicyModel:
    """策略模型测试"""
    
    def test_policy_creation(self, db_session, test_device):
        """测试策略创建"""
        from backend_server.app.models import Policy
        
        # 创建应用模式策略
        app_policy = Policy(
            device_id=test_device.id,
            mode="app",
            target_app_package="com.example.app"
        )
        db_session.add(app_policy)
        db_session.commit()
        
        assert app_policy.id is not None
        assert app_policy.mode == "app"
        assert app_policy.target_app_package == "com.example.app"
        assert app_policy.target_hdmi_port is None
        
        # 创建HDMI模式策略
        hdmi_policy = Policy(
            device_id=test_device.id,
            mode="hdmi",
            target_hdmi_port=2
        )
        db_session.add(hdmi_policy)
        db_session.commit()
        
        assert hdmi_policy.id is not None
        assert hdmi_policy.mode == "hdmi"
        assert hdmi_policy.target_hdmi_port == 2
        assert hdmi_policy.target_app_package is None
    
    def test_policy_hdmi_mode(self, db_session, test_device):
        """测试HDMI模式策略"""
        from backend_server.app.models import Policy
        
        # 测试有效的HDMI端口
        for port in [1, 2, 3, 4]:
            policy = Policy(
                device_id=test_device.id,
                mode="hdmi",
                target_hdmi_port=port
            )
            db_session.add(policy)
            db_session.commit()
            db_session.delete(policy)
            db_session.commit()
    
    def test_policy_update(self, db_session, test_policy):
        """测试策略更新"""
        # 从应用模式切换到HDMI模式
        test_policy.mode = "hdmi"
        test_policy.target_app_package = None
        test_policy.target_hdmi_port = 3
        
        db_session.commit()
        db_session.refresh(test_policy)
        
        assert test_policy.mode == "hdmi"
        assert test_policy.target_app_package is None
        assert test_policy.target_hdmi_port == 3
    
    def test_policy_cascade_delete(self, db_session, test_device):
        """测试策略级联删除"""
        from backend_server.app.models import Policy
        
        # 创建多个策略
        policies = []
        for i in range(3):
            policy = Policy(
                device_id=test_device.id,
                mode="app",
                target_app_package=f"com.example.app{i}"
            )
            db_session.add(policy)
            policies.append(policy)
        
        db_session.commit()
        
        # 删除设备（应该级联删除策略）
        db_session.delete(test_device)
        db_session.commit()
        
        # 验证策略已被删除
        for policy in policies:
            deleted_policy = db_session.query(Policy).filter(Policy.id == policy.id).first()
            assert deleted_policy is None
    
    def test_policy_validation(self):
        """测试策略验证"""
        from backend_server.app.models import Policy
        
        # 测试无效模式
        with pytest.raises(ValueError):
            Policy(mode="invalid_mode")
        
        # 测试HDMI模式缺少端口
        policy = Policy(mode="hdmi")
        assert policy.target_hdmi_port is None
        
        # 测试应用模式缺少包名
        policy = Policy(mode="app")
        assert policy.target_app_package is None

@pytest.mark.unit
class TestOperationModel:
    """操作记录模型测试"""
    
    def test_operation_creation(self, db_session, test_device):
        """测试操作记录创建"""
        from backend_server.app.models import Operation
        
        # 创建不同类型的操作记录
        operation_types = ["install", "uninstall", "start", "stop", "screenshot", "remote_control"]
        
        for op_type in operation_types:
            operation = Operation(
                device_id=test_device.id,
                operation_type=op_type,
                details=f"测试{op_type}操作"
            )
            db_session.add(operation)
            db_session.commit()
            
            assert operation.id is not None
            assert operation.operation_type == op_type
            assert operation.details == f"测试{op_type}操作"
            assert operation.created_at is not None
            
            db_session.delete(operation)
            db_session.commit()
    
    def test_operation_types(self, db_session, test_device):
        """测试操作类型"""
        from backend_server.app.models import Operation
        
        # 测试有效的操作类型
        valid_types = ["install", "uninstall", "start", "stop", "screenshot", 
                      "remote_control", "policy_update", "device_register"]
        
        for op_type in valid_types:
            operation = Operation(
                device_id=test_device.id,
                operation_type=op_type,
                details=f"测试{op_type}"
            )
            db_session.add(operation)
            db_session.commit()
            
            assert operation.operation_type == op_type
            
            db_session.delete(operation)
            db_session.commit()
    
    def test_operation_relationships(self, db_session, test_device):
        """测试操作记录关系"""
        from backend_server.app.models import Operation
        
        # 创建操作记录
        operation = Operation(
            device_id=test_device.id,
            operation_type="install",
            details="测试安装操作"
        )
        db_session.add(operation)
        db_session.commit()
        
        # 验证与设备的关系
        assert operation.device.id == test_device.id
        assert operation.device.device_name == test_device.device_name
        
        # 验证设备与操作记录的关系
        db_session.refresh(test_device)
        assert len(test_device.operations) == 1
        assert test_device.operations[0].id == operation.id
        
        db_session.delete(operation)
        db_session.commit()
    
    def test_operation_timestamp(self, db_session, test_device):
        """测试操作时间戳"""
        from backend_server.app.models import Operation
        import time
        
        # 创建第一个操作记录
        operation1 = Operation(
            device_id=test_device.id,
            operation_type="install",
            details="第一个操作"
        )
        db_session.add(operation1)
        db_session.commit()
        
        time.sleep(0.1)  # 等待一小段时间
        
        # 创建第二个操作记录
        operation2 = Operation(
            device_id=test_device.id,
            operation_type="uninstall",
            details="第二个操作"
        )
        db_session.add(operation2)
        db_session.commit()
        
        # 验证时间戳顺序
        assert operation2.created_at > operation1.created_at
        
        db_session.delete(operation1)
        db_session.delete(operation2)
        db_session.commit()

@pytest.mark.unit
class TestModelRelationships:
    """模型关系测试"""
    
    def test_device_policy_relationship(self, db_session):
        """测试设备-策略关系"""
        from backend_server.app.models import Device, Policy
        
        # 创建设备
        device = Device(
            device_name="关系测试设备",
            mac_address="AA:BB:CC:DD:EE:FF",
            ip_address="192.168.1.200"
        )
        db_session.add(device)
        db_session.commit()
        
        # 创建多个策略
        policies = []
        for i in range(3):
            policy = Policy(
                device_id=device.id,
                mode="app",
                target_app_package=f"com.test.app{i}"
            )
            db_session.add(policy)
            policies.append(policy)
        
        db_session.commit()
        
        # 刷新设备以获取关系
        db_session.refresh(device)
        
        # 验证关系
        assert len(device.policies) == 3
        for i, policy in enumerate(device.policies):
            assert policy.target_app_package == f"com.test.app{i}"
            assert policy.device.id == device.id
        
        # 清理
        for policy in policies:
            db_session.delete(policy)
        db_session.delete(device)
        db_session.commit()
    
    def test_device_operation_relationship(self, db_session):
        """测试设备-操作记录关系"""
        from backend_server.app.models import Device, Operation
        
        # 创建设备
        device = Device(
            device_name="操作测试设备",
            mac_address="11:22:33:44:55:66",
            ip_address="192.168.1.201"
        )
        db_session.add(device)
        db_session.commit()
        
        # 创建多个操作记录
        operations = []
        for i in range(5):
            operation = Operation(
                device_id=device.id,
                operation_type="test",
                details=f"测试操作{i}"
            )
            db_session.add(operation)
            operations.append(operation)
        
        db_session.commit()
        
        # 刷新设备以获取关系
        db_session.refresh(device)
        
        # 验证关系
        assert len(device.operations) == 5
        for i, operation in enumerate(device.operations):
            assert operation.details == f"测试操作{i}"
            assert operation.device.id == device.id
        
        # 清理
        for operation in operations:
            db_session.delete(operation)
        db_session.delete(device)
        db_session.commit()
    
    def test_cascade_operations(self, db_session):
        """测试级联操作"""
        from backend_server.app.models import Device, Policy, Operation
        
        # 创建设备
        device = Device(
            device_name="级联测试设备",
            mac_address="66:77:88:99:AA:BB",
            ip_address="192.168.1.202"
        )
        db_session.add(device)
        db_session.commit()
        
        # 创建策略
        policy = Policy(
            device_id=device.id,
            mode="app",
            target_app_package="com.cascade.test"
        )
        db_session.add(policy)
        db_session.commit()
        
        # 创建操作记录
        operation = Operation(
            device_id=device.id,
            operation_type="cascade_test",
            details="级联测试"
        )
        db_session.add(operation)
        db_session.commit()
        
        # 获取ID用于后续验证
        device_id = device.id
        policy_id = policy.id
        operation_id = operation.id
        
        # 删除设备（应该级联删除策略和操作记录）
        db_session.delete(device)
        db_session.commit()
        
        # 验证所有相关记录已被删除
        assert db_session.query(Device).filter(Device.id == device_id).first() is None
        assert db_session.query(Policy).filter(Policy.id == policy_id).first() is None
        assert db_session.query(Operation).filter(Operation.id == operation_id).first() is None