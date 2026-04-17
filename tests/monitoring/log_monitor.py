"""
日志监控器
负责收集和分析电视机日志
"""
import logging
import re
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from .monitor_config import MonitorConfig

class LogMonitor:
    """日志监控器"""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.logger = logging.getLogger("LogMonitor")
        
        # 日志模式
        self.log_patterns = {
            "error": re.compile(r'(error|exception|failed|crash|fatal)', re.IGNORECASE),
            "warning": re.compile(r'(warning|deprecated|obsolete)', re.IGNORECASE),
            "adb": re.compile(r'(adb|connected|disconnected|unauthorized)', re.IGNORECASE),
            "network": re.compile(r'(network|wifi|ethernet|ip|dhcp)', re.IGNORECASE),
            "app": re.compile(r'(app|package|activity|launch)', re.IGNORECASE),
            "system": re.compile(r'(system|boot|shutdown|reboot)', re.IGNORECASE),
        }
        
        # 日志缓存
        self.log_cache: List[Dict[str, Any]] = []
        self.last_log_check = datetime.now()
    
    def collect_logs(self) -> Dict[str, Any]:
        """收集日志"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "log_count": 0,
            "errors": [],
            "warnings": [],
            "new_entries": [],
            "summary": {},
        }
        
        try:
            # 收集系统日志
            system_logs = self._collect_system_logs()
            
            # 收集ADB日志
            adb_logs = self._collect_adb_logs()
            
            # 合并日志
            all_logs = system_logs + adb_logs
            
            # 分析日志
            if all_logs:
                analysis = self._analyze_logs(all_logs)
                
                result["log_count"] = len(all_logs)
                result["errors"] = analysis.get("errors", [])
                result["warnings"] = analysis.get("warnings", [])
                result["new_entries"] = analysis.get("new_entries", [])
                result["summary"] = analysis.get("summary", {})
                
                # 更新缓存
                self._update_log_cache(all_logs)
            
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"收集日志失败: {e}")
        
        return result
    
    def _collect_system_logs(self) -> List[Dict[str, Any]]:
        """收集系统日志"""
        logs = []
        
        try:
            # 通过ADB获取logcat日志
            import subprocess
            
            cmd = [
                "adb", "-s", f"{self.config.tv_ip}:{self.config.tv_port}",
                "logcat", "-d", "-v", "time"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                
                for line in lines:
                    if line.strip():
                        log_entry = self._parse_log_line(line)
                        if log_entry:
                            logs.append(log_entry)
            
        except Exception as e:
            self.logger.debug(f"收集系统日志失败: {e}")
        
        return logs
    
    def _collect_adb_logs(self) -> List[Dict[str, Any]]:
        """收集ADB日志"""
        logs = []
        
        try:
            # 获取ADB设备信息
            import subprocess
            
            cmd = [
                "adb", "-s", f"{self.config.tv_ip}:{self.config.tv_port}",
                "devices", "-l"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "level": "info",
                    "tag": "adb",
                    "message": f"ADB设备状态: {result.stdout.strip()}",
                    "source": "adb",
                }
                logs.append(log_entry)
            
        except Exception as e:
            self.logger.debug(f"收集ADB日志失败: {e}")
        
        return logs
    
    def _parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """解析日志行"""
        try:
            # 尝试解析标准logcat格式
            # 格式: MM-DD HH:MM:SS.mmm PID TID Level Tag: Message
            pattern = r'(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+([VDIWE])\s+([^:]+):\s+(.+)'
            match = re.match(pattern, line)
            
            if match:
                timestamp_str, pid, tid, level_char, tag, message = match.groups()
                
                # 转换级别字符
                level_map = {
                    'V': 'verbose',
                    'D': 'debug',
                    'I': 'info',
                    'W': 'warning',
                    'E': 'error',
                }
                
                level = level_map.get(level_char, 'unknown')
                
                # 解析时间戳
                try:
                    # 添加当前年份
                    current_year = datetime.now().year
                    timestamp_str = f"{current_year}-{timestamp_str}"
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
                except:
                    timestamp = datetime.now()
                
                return {
                    "timestamp": timestamp.isoformat(),
                    "level": level,
                    "tag": tag.strip(),
                    "message": message.strip(),
                    "pid": int(pid),
                    "tid": int(tid),
                    "source": "logcat",
                }
            
            # 如果不是标准格式，创建简单条目
            return {
                "timestamp": datetime.now().isoformat(),
                "level": "info",
                "tag": "unknown",
                "message": line.strip(),
                "source": "logcat",
            }
            
        except Exception as e:
            self.logger.debug(f"解析日志行失败: {e}")
            return None
    
    def _analyze_logs(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析日志"""
        analysis = {
            "errors": [],
            "warnings": [],
            "new_entries": [],
            "summary": {
                "total": len(logs),
                "by_level": {},
                "by_tag": {},
                "by_source": {},
            },
        }
        
        # 统计信息
        for log in logs:
            # 按级别统计
            level = log.get("level", "unknown")
            analysis["summary"]["by_level"][level] = analysis["summary"]["by_level"].get(level, 0) + 1
            
            # 按标签统计
            tag = log.get("tag", "unknown")
            analysis["summary"]["by_tag"][tag] = analysis["summary"]["by_tag"].get(tag, 0) + 1
            
            # 按来源统计
            source = log.get("source", "unknown")
            analysis["summary"]["by_source"][source] = analysis["summary"]["by_source"].get(source, 0) + 1
            
            # 检查错误和警告
            message = log.get("message", "").lower()
            
            if level == "error" or self.log_patterns["error"].search(message):
                analysis["errors"].append(log)
            elif level == "warning" or self.log_patterns["warning"].search(message):
                analysis["warnings"].append(log)
            
            # 检查新日志条目（自上次检查以来）
            log_time = datetime.fromisoformat(log["timestamp"].replace('Z', '+00:00'))
            if log_time > self.last_log_check:
                analysis["new_entries"].append(log)
        
        # 更新最后检查时间
        self.last_log_check = datetime.now()
        
        # 限制返回数量
        analysis["errors"] = analysis["errors"][-20:]  # 最近20个错误
        analysis["warnings"] = analysis["warnings"][-20:]  # 最近20个警告
        analysis["new_entries"] = analysis["new_entries"][-50:]  # 最近50个新条目
        
        return analysis
    
    def _update_log_cache(self, logs: List[Dict[str, Any]]):
        """更新日志缓存"""
        self.log_cache.extend(logs)
        
        # 限制缓存大小
        if len(self.log_cache) > 1000:
            self.log_cache = self.log_cache[-1000:]
        
        # 保存到文件（如果启用）
        if self.config.enable_log_collection:
            self._save_logs_to_file(logs)
    
    def _save_logs_to_file(self, logs: List[Dict[str, Any]]):
        """保存日志到文件"""
        try:
            log_dir = self.config.get_directories()["logs"]
            date_str = datetime.now().strftime("%Y%m%d")
            log_file = log_dir / f"tv_logs_{date_str}.log"
            
            with open(log_file, 'a', encoding='utf-8') as f:
                for log in logs:
                    line = f"{log['timestamp']} [{log['level'].upper()}] {log['tag']}: {log['message']}\n"
                    f.write(line)
            
        except Exception as e:
            self.logger.error(f"保存日志到文件失败: {e}")
    
    def search_logs(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """搜索日志"""
        results = []
        
        try:
            pattern = re.compile(query, re.IGNORECASE)
            
            for log in reversed(self.log_cache):  # 从最新开始搜索
                if (pattern.search(log.get("message", "")) or 
                    pattern.search(log.get("tag", ""))):
                    results.append(log)
                    
                    if len(results) >= max_results:
                        break
        
        except re.error:
            # 如果正则表达式无效，使用简单搜索
            query_lower = query.lower()
            for log in reversed(self.log_cache):
                if (query_lower in log.get("message", "").lower() or 
                    query_lower in log.get("tag", "").lower()):
                    results.append(log)
                    
                    if len(results) >= max_results:
                        break
        
        return results
    
    def get_log_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """获取日志统计信息"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 过滤指定时间范围内的日志
        recent_logs = []
        for log in self.log_cache:
            try:
                log_time = datetime.fromisoformat(log["timestamp"].replace('Z', '+00:00'))
                if log_time > cutoff_time:
                    recent_logs.append(log)
            except:
                continue
        
        statistics = {
            "period_hours": hours,
            "total_logs": len(recent_logs),
            "level_distribution": {},
            "tag_distribution": {},
            "source_distribution": {},
            "error_rate": 0,
            "warning_rate": 0,
        }
        
        if recent_logs:
            error_count = 0
            warning_count = 0
            
            for log in recent_logs:
                level = log.get("level", "unknown")
                tag = log.get("tag", "unknown")
                source = log.get("source", "unknown")
                
                # 统计分布
                statistics["level_distribution"][level] = statistics["level_distribution"].get(level, 0) + 1
                statistics["tag_distribution"][tag] = statistics["tag_distribution"].get(tag, 0) + 1
                statistics["source_distribution"][source] = statistics["source_distribution"].get(source, 0) + 1
                
                # 统计错误和警告
                if level == "error":
                    error_count += 1
                elif level == "warning":
                    warning_count += 1
            
            # 计算比率
            statistics["error_rate"] = round((error_count / len(recent_logs)) * 100, 2)
            statistics["warning_rate"] = round((warning_count / len(recent_logs)) * 100, 2)
        
        return statistics
    
    def clear_log_cache(self):
        """清理日志缓存"""
        cache_size = len(self.log_cache)
        self.log_cache.clear()
        self.logger.info(f"已清理日志缓存: {cache_size} 条记录")
    
    def export_logs(self, filepath: str, format: str = "json"):
        """导出日志"""
        try:
            if format == "json":
                import json
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(self.log_cache, f, indent=2, ensure_ascii=False)
            
            elif format == "text":
                with open(filepath, 'w', encoding='utf-8') as f:
                    for log in self.log_cache:
                        line = f"{log['timestamp']} [{log['level'].upper()}] {log['tag']}: {log['message']}\n"
                        f.write(line)
            
            else:
                raise ValueError(f"不支持的导出格式: {format}")
            
            self.logger.info(f"日志已导出到: {filepath} ({len(self.log_cache)} 条记录)")
            return True
            
        except Exception as e:
            self.logger.error(f"导出日志失败: {e}")
            return False