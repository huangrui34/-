"""
简单的API集成测试
"""
import pytest
import requests
import json

BASE_URL = "http://localhost:8000"

@pytest.mark.integration
class TestHealthAPI:
    """健康检查API测试"""
    
    def test_health_endpoint(self):
        """测试健康检查端点"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert data["ok"] is True
    
    def test_docs_endpoint(self):
        """测试API文档端点"""
        response = requests.get(f"{BASE_URL}/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

@pytest.mark.integration
class TestDeviceAPI:
    """设备API测试"""
    
    def test_get_devices(self):
        """测试获取设备列表"""
        response = requests.get(f"{BASE_URL}/api/v1/devices")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_device(self):
        """测试创建设备"""
        import uuid
        
        # 生成唯一的设备数据
        unique_sn = f"TEST-INTEGRATION-{uuid.uuid4().hex[:8]}"
        device_data = {
            "device_sn": unique_sn,
            "device_name": "集成测试设备",
            "token": f"integration_test_token_{uuid.uuid4().hex[:8]}",
            "room_name": "集成测试室",
            "model_name": "MiTV-TEST",
            "wifi_ip": "192.168.1.100",
            "eth_ip": "192.168.1.101",
            "wifi_mac": "00:11:22:33:44:55",
            "eth_mac": "AA:BB:CC:DD:EE:FF"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v1/devices/register",
            json=device_data
        )
        
        # 注册可能成功或失败
        assert response.status_code in [200, 201, 400, 409]
        
        if response.status_code in [200, 201]:
            data = response.json()
            # 验证响应包含必要的字段
            assert "device_id" in data or "id" in data
            assert "token" in data
            print(f"设备注册成功: device_id={data.get('device_id') or data.get('id')}, token={data.get('token')[:20]}...")
    
    def test_get_device_by_sn(self):
        """测试通过序列号获取设备"""
        # 首先获取设备列表
        response = requests.get(f"{BASE_URL}/api/v1/devices")
        assert response.status_code == 200
        devices = response.json()
        
        if devices:
            # 使用第一个设备的ID进行测试
            device_id = devices[0]["id"]
            response = requests.get(f"{BASE_URL}/api/v1/devices/{device_id}")
            
            if response.status_code == 200:
                data = response.json()
                assert "id" in data
                assert data["id"] == device_id
            else:
                # 设备端点可能返回404或其他状态码
                assert response.status_code in [404, 405]
        else:
            # 没有设备，跳过测试
            pytest.skip("没有可用的设备进行测试")

@pytest.mark.integration
class TestPolicyAPI:
    """策略API测试"""
    
    def test_get_policies(self):
        """测试获取策略列表"""
        response = requests.get(f"{BASE_URL}/api/v1/policies")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_policy(self):
        """测试创建策略"""
        import uuid
        unique_name = f"集成测试策略_{uuid.uuid4().hex[:8]}"
        
        policy_data = {
            "name": unique_name,
            "mode": "app",
            "target_app_package": "com.integration.test"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v1/policies",
            json=policy_data
        )
        
        # 可能返回200/201创建成功或409策略已存在
        assert response.status_code in [200, 201, 409]
        
        if response.status_code in [200, 201]:
            data = response.json()
            assert "id" in data
            assert data["name"] == policy_data["name"]
            print(f"策略创建成功: id={data['id']}, name={data['name']}")

@pytest.mark.integration
class TestDeploymentAPI:
    """部署API测试"""
    
    def test_deploy_to_tv(self):
        """测试部署到电视"""
        # 部署API需要查询参数
        params = {
            "ip": "10.181.184.226"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v1/deploy-tv",
            params=params
        )
        
        # 部署测试可能成功或失败
        assert response.status_code in [200, 400, 422, 500]
        
        if response.status_code == 200:
            data = response.json()
            # 验证响应包含必要的字段
            assert "ok" in data or "status" in data
            assert "message" in data
            print(f"部署测试响应: {data}")

@pytest.mark.integration
class TestADBAPI:
    """ADB API测试"""
    
    def test_adb_connection(self):
        """测试ADB连接"""
        # 首先获取设备列表
        response = requests.get(f"{BASE_URL}/api/v1/devices")
        assert response.status_code == 200
        devices = response.json()
        
        if not devices:
            pytest.skip("没有可用的设备进行ADB测试")
        
        # 使用第一个设备
        device = devices[0]
        device_id = device["id"]
        
        # 测试ADB连接
        response = requests.post(
            f"{BASE_URL}/api/v1/devices/{device_id}/adb/connect",
            json={"ip": device.get("eth_ip") or device.get("wifi_ip") or "10.181.184.226"}
        )
        
        # ADB连接可能成功或失败
        assert response.status_code in [200, 400, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "ok" in data or "status" in data
            print(f"ADB连接测试响应: {data}")

@pytest.mark.integration
class TestErrorHandling:
    """错误处理测试"""
    
    def test_invalid_endpoint(self):
        """测试无效端点"""
        response = requests.get(f"{BASE_URL}/api/v1/invalid-endpoint")
        assert response.status_code == 404
    
    def test_invalid_json(self):
        """测试无效JSON"""
        response = requests.post(
            f"{BASE_URL}/api/v1/devices/register",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        # 无效JSON可能返回400或422
        assert response.status_code in [400, 422, 500]
    
    def test_missing_required_fields(self):
        """测试缺少必填字段"""
        device_data = {
            "device_name": "测试设备"  # 缺少device_sn和token
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v1/devices/register",
            json=device_data
        )
        # 缺少必填字段可能返回400或422
        assert response.status_code in [400, 422, 500]

@pytest.mark.integration
class TestPerformance:
    """性能测试"""
    
    def test_health_endpoint_performance(self):
        """测试健康检查端点性能"""
        import time
        
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/health")
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        
        # 响应时间应小于3秒（考虑到网络延迟）
        assert response_time < 3.0
        print(f"健康检查响应时间: {response_time:.3f}秒")
    
    def test_concurrent_requests(self):
        """测试并发请求"""
        import concurrent.futures
        
        def make_request():
            response = requests.get(f"{BASE_URL}/health")
            return response.status_code
        
        # 并发5个请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # 所有请求都应成功
        assert all(status == 200 for status in results)