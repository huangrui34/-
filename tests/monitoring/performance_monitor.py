"""
性能监控器
负责收集电视机性能指标
"""
import time
import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime

from .monitor_config import MonitorConfig

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.logger = logging.getLogger("PerformanceMonitor")
    
    def collect_metrics(self) -> Dict[str, Any]:
        """收集性能指标"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "cpu_usage": None,
            "memory_usage": None,
            "storage_usage": None,
            "process_count": None,
            "temperature": None,
            "uptime": None,
        }
        
        try:
            # 收集CPU使用率
            if self.config.monitor_cpu:
                cpu_usage = self._get_cpu_usage()
                metrics["cpu_usage"] = cpu_usage
            
            # 收集内存使用率
            if self.config.monitor_memory:
                memory_usage = self._get_memory_usage()
                metrics["memory_usage"] = memory_usage
            
            # 收集存储使用率
            if self.config.monitor_storage:
                storage_usage = self._get_storage_usage()
                metrics["storage_usage"] = storage_usage
            
            # 收集进程数量
            process_count = self._get_process_count()
            metrics["process_count"] = process_count
            
            # 收集温度信息（如果可用）
            temperature = self._get_temperature()
            if temperature is not None:
                metrics["temperature"] = temperature
            
            # 收集运行时间
            uptime = self._get_uptime()
            if uptime is not None:
                metrics["uptime"] = uptime
            
            metrics["success"] = True
            
        except Exception as e:
            metrics["error"] = str(e)
            self.logger.error(f"收集性能指标失败: {e}")
        
        return metrics
    
    def _execute_adb_command(self, command: str) -> Optional[str]:
        """执行ADB命令"""
        try:
            import subprocess
            
            cmd = [
                "adb", "-s", f"{self.config.tv_ip}:{self.config.tv_port}",
                "shell", command
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                self.logger.warning(f"ADB命令失败: {command} - {result.stderr}")
                return None
                
        except Exception as e:
            self.logger.error(f"执行ADB命令异常 {command}: {e}")
            return None
    
    def _get_cpu_usage(self) -> Optional[float]:
        """获取CPU使用率"""
        try:
            # 读取/proc/stat获取CPU信息
            output = self._execute_adb_command("cat /proc/stat")
            if not output:
                return None
            
            # 解析第一行（总CPU使用情况）
            lines = output.split('\n')
            for line in lines:
                if line.startswith('cpu '):
                    parts = line.split()
                    # user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice
                    if len(parts) >= 5:
                        user = int(parts[1])
                        nice = int(parts[2])
                        system = int(parts[3])
                        idle = int(parts[4])
                        
                        total = user + nice + system + idle
                        if total > 0:
                            usage = ((user + nice + system) / total) * 100
                            return round(usage, 2)
                    break
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取CPU使用率失败: {e}")
            return None
    
    def _get_memory_usage(self) -> Optional[float]:
        """获取内存使用率"""
        try:
            output = self._execute_adb_command("cat /proc/meminfo")
            if not output:
                return None
            
            mem_total = None
            mem_available = None
            
            for line in output.split('\n'):
                if line.startswith('MemTotal:'):
                    parts = line.split()
                    if len(parts) >= 2:
                        mem_total = int(parts[1])
                elif line.startswith('MemAvailable:'):
                    parts = line.split()
                    if len(parts) >= 2:
                        mem_available = int(parts[1])
                elif line.startswith('MemFree:'):
                    parts = line.split()
                    if len(parts) >= 2 and mem_available is None:
                        mem_available = int(parts[1])
            
            if mem_total is not None and mem_available is not None and mem_total > 0:
                usage = ((mem_total - mem_available) / mem_total) * 100
                return round(usage, 2)
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取内存使用率失败: {e}")
            return None
    
    def _get_storage_usage(self) -> Optional[float]:
        """获取存储使用率"""
        try:
            output = self._execute_adb_command("df /data")
            if not output:
                return None
            
            lines = output.split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 5:
                    # 格式: Filesystem 1K-blocks Used Available Use% Mounted on
                    use_percent = parts[4]
                    if use_percent.endswith('%'):
                        usage = float(use_percent[:-1])
                        return round(usage, 2)
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取存储使用率失败: {e}")
            return None
    
    def _get_process_count(self) -> Optional[int]:
        """获取进程数量"""
        try:
            output = self._execute_adb_command("ps")
            if not output:
                return None
            
            # 计算非空行数（减去标题行）
            lines = output.strip().split('\n')
            if len(lines) > 1:
                return len(lines) - 1  # 减去标题行
            
            return 0
            
        except Exception as e:
            self.logger.error(f"获取进程数量失败: {e}")
            return None
    
    def _get_temperature(self) -> Optional[float]:
        """获取温度信息"""
        try:
            # 尝试读取温度传感器
            temp_files = [
                "/sys/class/thermal/thermal_zone0/temp",
                "/sys/class/thermal/thermal_zone1/temp",
                "/sys/devices/virtual/thermal/thermal_zone0/temp",
            ]
            
            for temp_file in temp_files:
                output = self._execute_adb_command(f"cat {temp_file} 2>/dev/null")
                if output and output.strip().isdigit():
                    temp = int(output.strip())
                    # 转换为摄氏度（通常是毫摄氏度）
                    if temp > 1000:  # 可能是毫摄氏度
                        temp = temp / 1000.0
                    return round(temp, 1)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"获取温度信息失败（可能不支持）: {e}")
            return None
    
    def _get_uptime(self) -> Optional[str]:
        """获取运行时间"""
        try:
            output = self._execute_adb_command("cat /proc/uptime")
            if not output:
                return None
            
            parts = output.split()
            if len(parts) >= 1:
                uptime_seconds = float(parts[0])
                
                # 转换为可读格式
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                seconds = int(uptime_seconds % 60)
                
                if days > 0:
                    return f"{days}d {hours}h {minutes}m"
                elif hours > 0:
                    return f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    return f"{minutes}m {seconds}s"
                else:
                    return f"{seconds}s"
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取运行时间失败: {e}")
            return None
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        metrics = self.collect_metrics()
        
        summary = {
            "timestamp": metrics.get("timestamp"),
            "success": metrics.get("success", False),
        }
        
        # CPU状态
        cpu_usage = metrics.get("cpu_usage")
        if cpu_usage is not None:
            if cpu_usage > 80:
                summary["cpu_status"] = "high"
            elif cpu_usage > 50:
                summary["cpu_status"] = "medium"
            else:
                summary["cpu_status"] = "low"
            summary["cpu_usage"] = cpu_usage
        
        # 内存状态
        memory_usage = metrics.get("memory_usage")
        if memory_usage is not None:
            if memory_usage > 85:
                summary["memory_status"] = "high"
            elif memory_usage > 60:
                summary["memory_status"] = "medium"
            else:
                summary["memory_status"] = "low"
            summary["memory_usage"] = memory_usage
        
        # 存储状态
        storage_usage = metrics.get("storage_usage")
        if storage_usage is not None:
            if storage_usage > 90:
                summary["storage_status"] = "critical"
            elif storage_usage > 80:
                summary["storage_status"] = "high"
            elif storage_usage > 60:
                summary["storage_status"] = "medium"
            else:
                summary["storage_status"] = "low"
            summary["storage_usage"] = storage_usage
        
        # 进程状态
        process_count = metrics.get("process_count")
        if process_count is not None:
            summary["process_count"] = process_count
        
        # 温度状态
        temperature = metrics.get("temperature")
        if temperature is not None:
            if temperature > 70:
                summary["temperature_status"] = "critical"
            elif temperature > 60:
                summary["temperature_status"] = "high"
            elif temperature > 50:
                summary["temperature_status"] = "medium"
            else:
                summary["temperature_status"] = "low"
            summary["temperature"] = temperature
        
        # 运行时间
        uptime = metrics.get("uptime")
        if uptime is not None:
            summary["uptime"] = uptime
        
        return summary