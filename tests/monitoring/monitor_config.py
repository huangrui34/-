"""
远程调试监控配置
用于实时监控电视机测试状态
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime

@dataclass
class MonitorConfig:
    """监控配置"""
    
    # 电视机信息
    tv_ip: str = "10.181.184.226"
    tv_port: int = 5555
    
    # 监控选项
    enable_screen_monitoring: bool = True
    enable_log_collection: bool = True
    enable_performance_monitoring: bool = True
    enable_network_monitoring: bool = True
    
    # 屏幕监控配置
    screenshot_interval: int = 5  # 截图间隔（秒）
    screenshot_quality: int = 80  # 截图质量（1-100）
    screenshot_max_count: int = 100  # 最大截图数量
    
    # 日志配置
    log_level: str = "INFO"
    log_retention_days: int = 7
    enable_remote_logging: bool = True
    
    # 性能监控配置
    monitor_cpu: bool = True
    monitor_memory: bool = True
    monitor_storage: bool = True
    monitor_network: bool = True
    performance_interval: int = 10  # 性能数据采集间隔（秒）
    
    # 网络监控配置
    ping_interval: int = 5  # Ping间隔（秒）
    network_timeout: int = 30  # 网络超时（秒）
    
    # 存储配置
    data_directory: str = "monitoring_data"
    screenshot_directory: str = "screenshots"
    log_directory: str = "logs"
    performance_directory: str = "performance"
    
    # 报警配置
    enable_alerts: bool = True
    alert_cpu_threshold: float = 80.0  # CPU使用率阈值（%）
    alert_memory_threshold: float = 85.0  # 内存使用率阈值（%）
    alert_storage_threshold: float = 90.0  # 存储使用率阈值（%）
    alert_network_latency_threshold: float = 200.0  # 网络延迟阈值（毫秒）
    
    # 通知配置
    enable_email_alerts: bool = False
    enable_webhook_alerts: bool = True
    webhook_url: Optional[str] = None
    
    # 实时监控配置
    enable_live_dashboard: bool = True
    dashboard_port: int = 8080
    dashboard_refresh_interval: int = 2  # 仪表板刷新间隔（秒）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def save(self, filepath: str):
        """保存配置到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: str) -> 'MonitorConfig':
        """从文件加载配置"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls(**data)
    
    def validate(self) -> List[str]:
        """验证配置，返回错误列表"""
        errors = []
        
        if not self.tv_ip:
            errors.append("电视机IP地址不能为空")
        
        if not 1 <= self.tv_port <= 65535:
            errors.append(f"端口号无效: {self.tv_port}")
        
        if self.screenshot_interval < 1:
            errors.append(f"截图间隔无效: {self.screenshot_interval}")
        
        if not 1 <= self.screenshot_quality <= 100:
            errors.append(f"截图质量无效: {self.screenshot_quality}")
        
        if self.performance_interval < 1:
            errors.append(f"性能采集间隔无效: {self.performance_interval}")
        
        if self.ping_interval < 1:
            errors.append(f"Ping间隔无效: {self.ping_interval}")
        
        return errors
    
    def get_directories(self) -> Dict[str, Path]:
        """获取所有目录路径"""
        base_dir = Path(self.data_directory)
        
        directories = {
            "base": base_dir,
            "screenshots": base_dir / self.screenshot_directory,
            "logs": base_dir / self.log_directory,
            "performance": base_dir / self.performance_directory,
        }
        
        # 创建目录
        for dir_path in directories.values():
            dir_path.mkdir(parents=True, exist_ok=True)
        
        return directories

# 默认配置
DEFAULT_CONFIG = MonitorConfig()

# 测试特定配置
TEST_CONFIG = MonitorConfig(
    tv_ip="10.181.184.226",
    tv_port=5555,
    screenshot_interval=3,  # 测试期间更频繁的截图
    performance_interval=5,  # 测试期间更频繁的性能监控
    enable_alerts=True,
    enable_live_dashboard=True,
    dashboard_port=8080,
)

# 生产配置
PRODUCTION_CONFIG = MonitorConfig(
    screenshot_interval=30,  # 生产环境减少截图频率
    performance_interval=60,  # 生产环境减少性能监控频率
    screenshot_max_count=1000,  # 生产环境保存更多截图
    log_retention_days=30,  # 生产环境保留更长时间的日志
    enable_alerts=True,
    enable_email_alerts=True,
    enable_live_dashboard=False,  # 生产环境可能不需要实时仪表板
)