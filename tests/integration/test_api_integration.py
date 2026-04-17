"""
API集成测试
测试API端点的完整功能流程
"""
import pytest
import time
from test_utils import api_client, data_gen, assertions, timer

@pytest.mark.integration
class TestDeviceAPI:
    """设备API集成测试"""
    
    def test_device_registration_flow(self, test_client):
        """测试设备注册完整流程"""
        api = api_client(test_client)
        
        # 1. 健康检查
        with timer("健康检查"):
            assert api.health_check(), "API服务不可用"
        
        # 2. 注册新设备
        device_data = data_gen.generate_device_data()
        
        with timer("设备注册"):
            response = api.register_device(device_data)
            assertions.assert_response_success(response)
            
            registered_device = response.json()
            assertions.assert_device_data(registered_device)
            
            # 保存设备ID用于后续测试
            device_id = registered_device["id"]
        
        # 3. 获取设备列表
        with timer("获取设备列表"):
            devices = api.get_devices()
            assert isinstance(devices, list)
            
            # 验证新注册的设备在列表中
            device_ids = [d["id"] for d in devices]
            assert device_id in device_ids
        
        # 4. 更新设备信息
        with timer("更新设备信息"):
            update_data = {
                "device_name": "更新后的设备名",
                "room_number": "Room888",
                "location": "新位置"
            }
            
            response = test_client.put(
                f"/api/v1/devices/{device_id}",
                json=update_data
            )
            assertions.assert_response_success(response)
            
            updated_device = response.json()
            assert updated_device["device_name"] == "更新后的设备名"
            assert updated_device["room_number"] == "Room888"
            assert updated_device["location"] == "新位置"
        
        # 5. 获取单个设备信息
        with timer("获取单个设备"):
            response = test_client.get(f"/api/v1/devices/{device_id}")
            assertions.assert_response_success(response)
            
            device = response.json()
            assert device["id"] == device_id
            assert device["device_name"] == "更新后的设备名"
        
        # 6. 删除设备
        with timer("删除设备"):
            response = test_client.delete(f"/api/v1/devices/{device_id}")
            assertions.assert_response_success(response, 200)
            
            # 验证设备已删除
            response = test_client.get(f"/api/v1/devices/{device_id}")
            assert response.status_code == 404
    
    def test_device_heartbeat(self, test_client):
        """测试设备心跳机制"""
        # 1. 注册设备
        device_data = data_gen.generate_device_data()
        response = test_client.post("/api/v1/devices/register", json=device_data)
        device_id = response.json()["id"]
        
        try:
            # 2. 发送心跳
            heartbeat_data = {
                "status": "online",
                "ip_address": "192.168.1.150"
            }
            
            with timer("发送心跳"):
                response = test_client.post(
                    f"/api/v1/devices/{device_id}/heartbeat",
                    json=heartbeat_data
                )
                assertions.assert_response_success(response)
                
                result = response.json()
                assert result["ok"] is True
                assert "last_seen" in result
            
            # 3. 验证设备状态更新
            response = test_client.get(f"/api/v1/devices/{device_id}")
            device = response.json()
            
            assert device["status"] == "online"
            assert device["ip_address"] == "192.168.1.150"
            assert device["last_seen"] is not None
            
        finally:
            # 清理
            test_client.delete(f"/api/v1/devices/{device_id}")
    
    def test_device_token_management(self, test_client):
        """测试设备令牌管理"""
        # 1. 注册设备
        device_data = data_gen.generate_device_data()
        response = test_client.post("/api/v1/devices/register", json=device_data)
        device = response.json()
        device_id = device["id"]
        
        try:
            # 2. 生成新令牌
            with timer("生成令牌"):
                response = test_client.post(f"/api/v1/devices/{device_id}/token")
                assertions.assert_response_success(response)
                
                token_data = response.json()
                assert "token" in token_data
                new_token = token_data["token"]
            
            # 3. 使用新令牌验证
            with timer("令牌验证"):
                verify_data = {"token": new_token}
                response = test_client.post(
                    f"/api/v1/devices/{device_id}/verify",
                    json=verify_data
                )
                assertions.assert_response_success(response)
                
                verify_result = response.json()
                assert verify_result["valid"] is True
            
            # 4. 清除令牌
            with timer("清除令牌"):
                response = test_client.delete(f"/api/v1/devices/{device_id}/token")
                assertions.assert_response_success(response)
                
                # 验证令牌已失效
                response = test_client.post(
                    f"/api/v1/devices/{device_id}/verify",
                    json=verify_data
                )
                verify_result = response.json()
                assert verify_result["valid"] is False
            
        finally:
            # 清理
            test_client.delete(f"/api/v1/devices/{device_id}")

@pytest.mark.integration
class TestPolicyAPI:
    """策略API集成测试"""
    
    def test_policy_management_flow(self, test_client):
        """测试策略管理完整流程"""
        # 1. 注册测试设备
        device_data = data_gen.generate_device_data()
        response = test_client.post("/api/v1/devices/register", json=device_data)
        device_id = response.json()["id"]
        
        try:
            # 2. 创建APP模式策略
            app_policy_data = {
                "mode": "app",
                "target_app_package": "com.android.settings"
            }
            
            with timer("创建APP策略"):
                response = test_client.post(
                    f"/api/v1/devices/{device_id}/policy",
                    json=app_policy_data
                )
                assertions.assert_response_success(response)
                
                policy = response.json()
                assertions.assert_policy_data(policy)
                assert policy["mode"] == "app"
                assert policy["target_app_package"] == "com.android.settings"
                policy_id = policy["id"]
            
            # 3. 获取设备策略
            with timer("获取策略"):
                response = test_client.get(f"/api/v1/devices/{device_id}/policy")
                assertions.assert_response_success(response)
                
                current_policy = response.json()
                assert current_policy["id"] == policy_id
                assert current_policy["device_id"] == device_id
            
            # 4. 更新为HDMI模式策略
            hdmi_policy_data = {
                "mode": "hdmi",
                "target_hdmi_port": 2
            }
            
            with timer("更新策略"):
                response = test_client.put(
                    f"/api/v1/devices/{device_id}/policy",
                    json=hdmi_policy_data
                )
                assertions.assert_response_success(response)
                
                updated_policy = response.json()
                assert updated_policy["mode"] == "hdmi"
                assert updated_policy["target_hdmi_port"] == 2
                assert updated_policy["target_app_package"] is None
            
            # 5. 删除策略
            with timer("删除策略"):
                response = test_client.delete(f"/api/v1/devices/{device_id}/policy")
                assertions.assert_response_success(response)
                
                # 验证策略已删除
                response = test_client.get(f"/api/v1/devices/{device_id}/policy")
                assert response.status_code == 404
        
        finally:
            # 清理设备
            test_client.delete(f"/api/v1/devices/{device_id}")
    
    def test_policy_execution(self, test_client):
        """测试策略执行"""
        # 1. 注册设备并创建策略
        device_data = data_gen.generate_device_data()
        response = test_client.post("/api/v1/devices/register", json=device_data)
        device_id = response.json()["id"]
        
        try:
            # 2. 创建策略
            policy_data = {
                "mode": "app",
                "target_app_package": "com.android.settings"
            }
            test_client.post(f"/api/v1/devices/{device_id}/policy", json=policy_data)
            
            # 3. 执行策略
            with timer("执行策略"):
                response = test_client.post(f"/api/v1/devices/{device_id}/execute")
                assertions.assert_response_success(response)
                
                result = response.json()
                assert result["ok"] is True
                assert "message" in result
            
            # 4. 验证操作记录
            response = test_client.get(f"/api/v1/devices/{device_id}/operations")
            operations = response.json()
            
            assert isinstance(operations, list)
            assert len(operations) > 0
            
            # 查找执行策略的操作记录
            execute_operations = [
                op for op in operations 
                if op["operation_type"] == "execute_policy"
            ]
            assert len(execute_operations) > 0
        
        finally:
            # 清理
            test_client.delete(f"/api/v1/devices/{device_id}")

@pytest.mark.integration
class TestRemoteControlAPI:
    """远程控制API集成测试"""
    
    def test_remote_control_operations(self, test_client):
        """测试远程控制操作"""
        # 1. 注册设备
        device_data = data_gen.generate_device_data()
        response = test_client.post("/api/v1/devices/register", json=device_data)
        device_id = response.json()["id"]
        
        try:
            # 2. 测试各种远程控制命令
            test_commands = [
                {"command": "keyevent", "keycode": 3, "description": "HOME键"},
                {"command": "keyevent", "keycode": 4, "description": "返回键"},
                {"command": "keyevent", "keycode": 82, "description": "菜单键"},
                {"command": "tap", "x": 100, "y": 100, "description": "点击屏幕"},
                {"command": "swipe", "x1": 100, "y1": 100, "x2": 200, "y2": 200, "description": "滑动"},
                {"command": "text", "text": "Hello", "description": "输入文本"},
            ]
            
            for cmd in test_commands:
                with timer(f"远程控制: {cmd['description']}"):
                    response = test_client.post(
                        f"/api/v1/devices/{device_id}/control",
                        json=cmd
                    )
                    assertions.assert_response_success(response)
                    
                    result = response.json()
                    assert result["ok"] is True
                    assert "message" in result
            
            # 3. 测试截图功能
            with timer("远程截图"):
                response = test_client.post(f"/api/v1/devices/{device_id}/screenshot")
                assertions.assert_response_success(response)
                
                result = response.json()
                assert result["ok"] is True
                assert "screenshot" in result or "message" in result
            
            # 4. 测试重启命令
            with timer("重启设备"):
                response = test_client.post(
                    f"/api/v1/devices/{device_id}/control",
                    json={"command": "reboot"}
                )
                # 重启可能成功或失败（取决于权限）
                assert response.status_code in [200, 403, 500]
        
        finally:
            # 清理
            test_client.delete(f"/api/v1/devices/{device_id}")
    
    def test_app_management(self, test_client):
        """测试应用管理功能"""
        # 1. 注册设备
        device_data = data_gen.generate_device_data()
        response = test_client.post("/api/v1/devices/register", json=device_data)
        device_id = response.json()["id"]
        
        try:
            # 2. 获取已安装应用列表
            with timer("获取应用列表"):
                response = test_client.get(f"/api/v1/devices/{device_id}/apps")
                assertions.assert_response_success(response)
                
                apps = response.json()
                assert isinstance(apps, list)
            
            # 3. 启动应用测试
            test_apps = ["com.android.settings", "com.android.chrome"]
            
            for app in test_apps:
                with timer(f"启动应用: {app}"):
                    response = test_client.post(
                        f"/api/v1/devices/{device_id}/launch",
                        json={"package_name": app}
                    )
                    # 应用可能不存在，所以接受404
                    if response.status_code not in [200, 404]:
                        response.raise_for_status()
            
            # 4. 停止应用测试
            with timer("停止应用"):
                response = test_client.post(
                    f"/api/v1/devices/{device_id}/stop",
                    json={"package_name": "com.android.settings"}
                )
                if response.status_code not in [200, 404]:
                    response.raise_for_status()
        
        finally:
            # 清理
            test_client.delete(f"/api/v1/devices/{device_id}")

@pytest.mark.integration
class TestScrcpyAPI:
    """Scrcpy API集成测试"""
    
    def test_scrcpy_management(self, test_client):
        """测试Scrcpy管理功能"""
        # 1. 注册设备
        device_data = data_gen.generate_device_data()
        response = test_client.post("/api/v1/devices/register", json=device_data)
        device_id = response.json()["id"]
        
        try:
            # 2. 检查Scrcpy安装状态
            with timer("检查Scrcpy安装"):
                response = test_client.get("/api/v1/scrcpy/check")
                assertions.assert_response_success(response)
                
                status = response.json()
                assert "installed" in status
                assert "message" in status
            
            # 3. 测试Scrcpy启动（模拟设备）
            with timer("启动Scrcpy"):
                response = test_client.post(f"/api/v1/devices/{device_id}/scrcpy/start")
                # 由于是模拟设备，可能无法真正启动Scrcpy
                # 但API应该返回合理的响应
                assert response.status_code in [200, 400, 500]
                
                if response.status_code == 200:
                    result = response.json()
                    assert "ok" in result
            
            # 4. 测试Scrcpy停止
            with timer("停止Scrcpy"):
                response = test_client.post(f"/api/v1/devices/{device_id}/scrcpy/stop")
                assertions.assert_response_success(response)
                
                result = response.json()
                assert "ok" in result
        
        finally:
            # 清理
            test_client.delete(f"/api/v1/devices/{device_id}")

@pytest.mark.integration
class TestOperationLogAPI:
    """操作日志API集成测试"""
    
    def test_operation_logging(self, test_client):
        """测试操作日志记录"""
        # 1. 注册设备
        device_data = data_gen.generate_device_data()
        response = test_client.post("/api/v1/devices/register", json=device_data)
        device_id = response.json()["id"]
        
        try:
            # 2. 执行多个操作
            operations = [
                {"type": "test_operation_1", "details": '{"test": 1}'},
                {"type": "test_operation_2", "details": '{"test": 2}'},
                {"type": "test_operation_3", "details": '{"test": 3}'},
            ]
            
            for op in operations:
                response = test_client.post(
                    f"/api/v1/devices/{device_id}/log",
                    json=op
                )
                assertions.assert_response_success(response)
            
            # 3. 获取操作日志
            with timer("获取操作日志"):
                response = test_client.get(f"/api/v1/devices/{device_id}/operations")
                assertions.assert_response_success(response)
                
                logs = response.json()
                assert isinstance(logs, list)
                assert len(logs) >= len(operations)
            
            # 4. 分页查询测试
            with timer("分页查询"):
                response = test_client.get(
                    f"/api/v1/devices/{device_id}/operations",
                    params={"page": 1, "per_page": 2}
                )
                assertions.assert_response_success(response)
                
                paged_logs = response.json()
                assert isinstance(paged_logs, list)
                assert len(paged_logs) <= 2
            
            # 5. 按类型过滤测试
            with timer("按类型过滤"):
                response = test_client.get(
                    f"/api/v1/devices/{device_id}/operations",
                    params={"type": "test_operation_1"}
                )
                assertions.assert_response_success(response)
                
                filtered_logs = response.json()
                assert isinstance(filtered_logs, list)
                if filtered_logs:
                    assert all(log["operation_type"] == "test_operation_1" 
                              for log in filtered_logs)
        
        finally:
            # 清理
            test_client.delete(f"/api/v1/devices/{device_id}")

@pytest.mark.integration
class TestErrorHandling:
    """错误处理集成测试"""
    
    def test_invalid_device_id(self, test_client):
        """测试无效设备ID"""
        invalid_ids = [-1, 0, 999999, "invalid", None]
        
        for device_id in invalid_ids:
            response = test_client.get(f"/api/v1/devices/{device_id}")
            assert response.status_code in [404, 422, 400]
    
    def test_invalid_policy_data(self, test_client):
        """测试无效策略数据"""
        # 1. 注册设备
        device_data = data_gen.generate_device_data()
        response = test_client.post("/api/v1/devices/register", json=device_data)
        device_id = response.json()["id"]
        
        try:
            # 2. 测试无效策略数据
            invalid_policies = [
                {"mode": "invalid_mode"},  # 无效模式
                {"mode": "app"},  # APP模式缺少包名
                {"mode": "hdmi", "target_hdmi_port": 0},  # 无效HDMI端口
                {"mode": "hdmi", "target_hdmi_port": 4},  # 无效HDMI端口
                {"mode": "hdmi", "target_app_package": "com.test.app"},  # HDMI模式不应有包名
                {},  # 空数据
                None,  # null数据
            ]
            
            for policy_data in invalid_policies:
                response = test_client.post(
                    f"/api/v1/devices/{device_id}/policy",
                    json=policy_data
                )
                assert response.status_code in [400, 422]
        
        finally:
            # 清理
            test_client.delete(f"/api/v1/devices/{device_id}")
    
    def test_missing_required_fields(self, test_client):
        """测试缺少必填字段"""
        # 测试设备注册缺少必填字段
        incomplete_data = [
            {"device_name": "Test"},  # 缺少MAC地址
            {"mac_address": "00:11:22:33:44:55"},  # 缺少设备名
            {},  # 空数据
        ]
        
        for data in incomplete_data:
            response = test_client.post("/api/v1/devices/register", json=data)
            assert response.status_code in [400, 422]
    
    def test_duplicate_registration(self, test_client):
        """测试重复注册"""
        # 1. 注册设备
        device_data = data_gen.generate_device_data()
        response = test_client.post("/api/v1/devices/register", json=device_data)
        device_id = response.json()["id"]
        
        try:
            # 2. 尝试用相同MAC地址再次注册
            response = test_client.post("/api/v1/devices/register", json=device_data)
            assert response.status_code in [400, 409, 422]
        
        finally:
            # 清理
            test_client.delete(f"/api/v1/devices/{device_id}")

@pytest.mark.integration
class TestPerformanceIntegration:
    """性能集成测试"""
    
    def test_concurrent_registrations(self, test_client):
        """测试并发设备注册"""
        import concurrent.futures
        
        device_count = 10
        devices_data = [data_gen.generate_device_data() for _ in range(device_count)]
        
        with timer(f"并发注册{device_count}个设备"):
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(
                        test_client.post,
                        "/api/v1/devices/register",
                        json=device_data
                    )
                    for device_data in devices_data
                ]
                
                results = []
                for future in concurrent.futures.as_completed(futures):
                    try:
                        response = future.result()
                        results.append(response)
                    except Exception as e:
                        print(f"并发注册失败: {e}")
                
                # 验证大多数请求成功
                success_count = sum(1 for r in results if r.status_code == 200)
                assert success_count >= device_count * 0.8  # 80%成功率
        
        # 清理
        for response in results:
            if response.status_code == 200:
                device_id = response.json()["id"]
                test_client.delete(f"/api/v1/devices/{device_id}")
    
    def test_bulk_operations(self, test_client):
        """测试批量操作性能"""
        # 1. 批量创建设备
        batch_size = 20
        devices = []
        
        with timer(f"批量创建{batch_size}个设备"):
            for i in range(batch_size):
                device_data = data_gen.generate_device_data(
                    device_name=f"BatchDevice_{i}"
                )
                response = test_client.post("/api/v1/devices/register", json=device_data)
                if response.status_code == 200:
                    devices.append(response.json())
        
        try:
            # 2. 批量更新策略
            with timer(f"批量更新{batch_size}个设备的策略"):
                for device in devices:
                    policy_data = {
                        "mode": "app",
                        "target_app_package": "com.android.settings"
                    }
                    test_client.post(
                        f"/api/v1/devices/{device['id']}/policy",
                        json=policy_data
                    )
            
            # 3. 批量查询性能
            with timer("批量查询设备列表"):
                response = test_client.get("/api/v1/devices")
                assertions.assert_response_success(response)
                
                all_devices = response.json()
                assert isinstance(all_devices, list)
                assert len(all_devices) >= batch_size
            
            # 4. 验证响应时间
            max_query_time = 2.0  # 最大查询时间（秒）
            assert timer.get_duration() <= max_query_time
        
        finally:
            # 5. 批量清理
            with timer(f"批量删除{batch_size}个设备"):
                for device in devices:
                    test_client.delete(f"/api/v1/devices/{device['id']}")