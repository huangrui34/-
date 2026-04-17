"""
网络监控器
负责监控电视机网络连接状态
"""
import time
import logging
import socket
import subprocess
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from statistics import mean, stdev

from .monitor_config import MonitorConfig

class NetworkMonitor:
    """网络监控器"""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.logger = logging.getLogger("NetworkMonitor")
        
        # 网络统计
        self.ping_results = []
        self.connection_status_history = []
        
    def check_network(self) -> Dict[str, Any]:
        """检查网络连接"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "connected": False,
            "latency": None,
            "packet_loss": None,
            "bandwidth": None,
            "error": None,
        }
        
        try:
            # 1. 检查基本连接
            connected = self._check_connectivity()
            result["connected"] = connected
            
            if not connected:
                result["error"] = "无法连接到电视机"
                return result
            
            # 2. 测量延迟
            latency = self._measure_latency()
            if latency is not None:
                result["latency"] = latency
                self.ping_results.append(latency)
                
                # 限制历史记录大小
                if len(self.ping_results) > 100:
                    self.ping_results = self.ping_results[-100:]
            
            # 3. 测量带宽（可选）
            if self.config.monitor_network:
                bandwidth = self._measure_bandwidth()
                if bandwidth is not None:
                    result["bandwidth"] = bandwidth
            
            # 4. 记录连接状态
            self.connection_status_history.append({
                "timestamp": result["timestamp"],
                "connected": connected,
                "latency": latency,
            })
            
            if len(self.connection_status_history) > 100:
                self.connection_status_history = self.connection_status_history[-100:]
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"网络检查失败: {e}")
        
        return result
    
    def _check_connectivity(self) -> bool:
        """检查基本连接性"""
        try:
            # 尝试ADB连接
            cmd = [
                "adb", "-s", f"{self.config.tv_ip}:{self.config.tv_port}",
                "shell", "echo", "test"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.network_timeout
            )
            
            return result.returncode == 0 and "test" in result.stdout
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
        except Exception as e:
            self.logger.debug(f"连接检查异常: {e}")
            return False
    
    def _measure_latency(self, count: int = 3) -> Optional[float]:
        """测量网络延迟（ping）"""
        try:
            latencies = []
            
            for i in range(count):
                start_time = time.time()
                
                # 使用ADB命令测试延迟
                cmd = [
                    "adb", "-s", f"{self.config.tv_ip}:{self.config.tv_port}",
                    "shell", "echo", "ping_test"
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and "ping_test" in result.stdout:
                    end_time = time.time()
                    latency = (end_time - start_time) * 1000  # 转换为毫秒
                    latencies.append(latency)
                
                # 短暂延迟
                if i < count - 1:
                    time.sleep(0.5)
            
            if latencies:
                return round(mean(latencies), 2)
            else:
                return None
                
        except Exception as e:
            self.logger.debug(f"延迟测量失败: {e}")
            return None
    
    def _measure_bandwidth(self) -> Optional[float]:
        """测量网络带宽"""
        try:
            # 创建测试文件（1MB）
            test_size = 1024 * 1024  # 1MB
            test_file = "/sdcard/bandwidth_test.bin"
            
            # 创建测试文件
            create_cmd = [
                "adb", "-s", f"{self.config.tv_ip}:{self.config.tv_port}",
                "shell", f"dd if=/dev/zero of={test_file} bs=1024 count=1024 2>/dev/null"
            ]
            
            start_time = time.time()
            result = subprocess.run(
                create_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            end_time = time.time()
            
            if result.returncode != 0:
                return None
            
            # 计算带宽（MB/s）
            duration = end_time - start_time
            if duration > 0:
                bandwidth = (test_size / (1024 * 1024)) / duration  # MB/s
                
                # 清理测试文件
                cleanup_cmd = [
                    "adb", "-s", f"{self.config.tv_ip}:{self.config.tv_port}",
                    "shell", f"rm {test_file}"
                ]
                subprocess.run(cleanup_cmd, capture_output=True, timeout=5)
                
                return round(bandwidth, 2)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"带宽测量失败: {e}")
            return None
    
    def get_network_summary(self) -> Dict[str, Any]:
        """获取网络摘要"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "connection_status": "unknown",
            "latency_stats": {},
            "connection_history": [],
        }
        
        # 检查当前连接状态
        current_status = self._check_connectivity()
        summary["current_connected"] = current_status
        summary["connection_status"] = "connected" if current_status else "disconnected"
        
        # 计算延迟统计
        if self.ping_results:
            summary["latency_stats"] = {
                "current": self.ping_results[-1] if self.ping_results else None,
                "average": round(mean(self.ping_results), 2) if len(self.ping_results) > 1 else None,
                "min": round(min(self.ping_results), 2) if self.ping_results else None,
                "max": round(max(self.ping_results), 2) if self.ping_results else None,
                "std_dev": round(stdev(self.ping_results), 2) if len(self.ping_results) > 1 else None,
                "count": len(self.ping_results),
            }
        
        # 连接历史（最近10次）
        summary["connection_history"] = self.connection_status_history[-10:]
        
        # 计算连接稳定性
        if self.connection_status_history:
            recent_history = self.connection_status_history[-20:]  # 最近20次
            if recent_history:
                connected_count = sum(1 for h in recent_history if h.get("connected"))
                stability = (connected_count / len(recent_history)) * 100
                summary["stability"] = round(stability, 1)
        
        return summary
    
    def test_port(self, port: int, timeout: int = 5) -> bool:
        """测试特定端口是否开放"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            result = sock.connect_ex((self.config.tv_ip, port))
            sock.close()
            
            return result == 0
            
        except Exception as e:
            self.logger.debug(f"端口测试失败 {port}: {e}")
            return False
    
    def get_open_ports(self, ports_to_test: list = None) -> Dict[int, bool]:
        """获取开放端口"""
        if ports_to_test is None:
            ports_to_test = [5555, 22, 80, 443, 8080, 8081]
        
        results = {}
        for port in ports_to_test:
            results[port] = self.test_port(port)
        
        return results
    
    def diagnose_network_issue(self) -> Dict[str, Any]:
        """诊断网络问题"""
        diagnosis = {
            "timestamp": datetime.now().isoformat(),
            "issues": [],
            "suggestions": [],
        }
        
        # 检查ADB连接
        adb_connected = self._check_connectivity()
        if not adb_connected:
            diagnosis["issues"].append("ADB连接失败")
            diagnosis["suggestions"].append("检查电视机ADB调试是否开启")
            diagnosis["suggestions"].append("检查网络连接是否正常")
            diagnosis["suggestions"].append("尝试重新连接ADB")
        
        # 检查延迟
        latency = self._measure_latency()
        if latency is not None:
            if latency > 100:  # 100ms以上为高延迟
                diagnosis["issues"].append(f"网络延迟过高: {latency}ms")
                diagnosis["suggestions"].append("检查网络质量")
                diagnosis["suggestions"].append("减少网络负载")
            elif latency > 50:
                diagnosis["issues"].append(f"网络延迟偏高: {latency}ms")
        
        # 检查端口
        common_ports = self.get_open_ports()
        closed_ports = [port for port, open in common_ports.items() if not open]
        if closed_ports:
            diagnosis["issues"].append(f"以下端口关闭: {closed_ports}")
        
        # 如果没有问题
        if not diagnosis["issues"] and adb_connected:
            diagnosis["status"] = "正常"
            diagnosis["message"] = "网络连接正常"
        
        return diagnosis