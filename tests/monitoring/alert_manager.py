"""
报警管理器
负责监控异常情况并触发报警
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from .monitor_config import MonitorConfig

class AlertManager:
    """报警管理器"""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.logger = logging.getLogger("AlertManager")
        
        # 报警历史
        self.alert_history: List[Dict[str, Any]] = []
        
        # 报警抑制（避免重复报警）
        self.suppressed_alerts: Dict[str, datetime] = {}
        
        # 报警规则
        self.alert_rules = self._initialize_alert_rules()
    
    def _initialize_alert_rules(self) -> List[Dict[str, Any]]:
        """初始化报警规则"""
        rules = [
            # CPU报警规则
            {
                "type": "cpu_high",
                "condition": lambda data: data.get("cpu_usage", 0) > self.config.alert_cpu_threshold,
                "level": "warning",
                "message": "CPU使用率过高",
                "details_template": "CPU使用率: {cpu_usage}% (阈值: {threshold}%)",
                "suppression_minutes": 5,  # 5分钟内不重复报警
            },
            {
                "type": "cpu_critical",
                "condition": lambda data: data.get("cpu_usage", 0) > 90,
                "level": "critical",
                "message": "CPU使用率严重过高",
                "details_template": "CPU使用率: {cpu_usage}% (超过90%)",
                "suppression_minutes": 2,
            },
            
            # 内存报警规则
            {
                "type": "memory_high",
                "condition": lambda data: data.get("memory_usage", 0) > self.config.alert_memory_threshold,
                "level": "warning",
                "message": "内存使用率过高",
                "details_template": "内存使用率: {memory_usage}% (阈值: {threshold}%)",
                "suppression_minutes": 5,
            },
            {
                "type": "memory_critical",
                "condition": lambda data: data.get("memory_usage", 0) > 95,
                "level": "critical",
                "message": "内存使用率严重过高",
                "details_template": "内存使用率: {memory_usage}% (超过95%)",
                "suppression_minutes": 2,
            },
            
            # 存储报警规则
            {
                "type": "storage_high",
                "condition": lambda data: data.get("storage_usage", 0) > self.config.alert_storage_threshold,
                "level": "warning",
                "message": "存储空间不足",
                "details_template": "存储使用率: {storage_usage}% (阈值: {threshold}%)",
                "suppression_minutes": 10,
            },
            {
                "type": "storage_critical",
                "condition": lambda data: data.get("storage_usage", 0) > 95,
                "level": "critical",
                "message": "存储空间严重不足",
                "details_template": "存储使用率: {storage_usage}% (超过95%)",
                "suppression_minutes": 5,
            },
            
            # 网络报警规则
            {
                "type": "network_high_latency",
                "condition": lambda data: data.get("latency", 0) > self.config.alert_network_latency_threshold,
                "level": "warning",
                "message": "网络延迟过高",
                "details_template": "网络延迟: {latency}ms (阈值: {threshold}ms)",
                "suppression_minutes": 3,
            },
            {
                "type": "network_disconnected",
                "condition": lambda data: data.get("connected") is False,
                "level": "critical",
                "message": "网络连接断开",
                "details_template": "无法连接到电视机",
                "suppression_minutes": 1,
            },
            
            # 进程报警规则
            {
                "type": "process_high",
                "condition": lambda data: data.get("process_count", 0) > 200,
                "level": "warning",
                "message": "进程数量过多",
                "details_template": "进程数量: {process_count} (超过200)",
                "suppression_minutes": 10,
            },
            
            # 温度报警规则
            {
                "type": "temperature_high",
                "condition": lambda data: data.get("temperature", 0) > 70,
                "level": "critical",
                "message": "温度过高",
                "details_template": "温度: {temperature}°C (超过70°C)",
                "suppression_minutes": 2,
            },
            {
                "type": "temperature_warning",
                "condition": lambda data: data.get("temperature", 0) > 60,
                "level": "warning",
                "message": "温度偏高",
                "details_template": "温度: {temperature}°C (超过60°C)",
                "suppression_minutes": 5,
            },
        ]
        
        return rules
    
    def check_performance_alerts(self, performance_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查性能报警"""
        alerts = []
        
        for rule in self.alert_rules:
            # 只检查性能相关报警
            if not rule["type"].startswith(("cpu_", "memory_", "storage_", "process_", "temperature_")):
                continue
            
            try:
                if rule["condition"](performance_data):
                    alert = self._create_alert(rule, performance_data)
                    if alert and not self._is_suppressed(alert["type"]):
                        alerts.append(alert)
                        self._suppress_alert(alert["type"], rule.get("suppression_minutes", 5))
            except Exception as e:
                self.logger.error(f"检查报警规则失败 {rule['type']}: {e}")
        
        return alerts
    
    def check_network_alerts(self, network_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查网络报警"""
        alerts = []
        
        for rule in self.alert_rules:
            # 只检查网络相关报警
            if not rule["type"].startswith("network_"):
                continue
            
            try:
                if rule["condition"](network_data):
                    alert = self._create_alert(rule, network_data)
                    if alert and not self._is_suppressed(alert["type"]):
                        alerts.append(alert)
                        self._suppress_alert(alert["type"], rule.get("suppression_minutes", 5))
            except Exception as e:
                self.logger.error(f"检查报警规则失败 {rule['type']}: {e}")
        
        return alerts
    
    def _create_alert(self, rule: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """创建报警"""
        try:
            # 格式化详细信息
            details = rule.get("details_template", "").format(
                cpu_usage=data.get("cpu_usage"),
                memory_usage=data.get("memory_usage"),
                storage_usage=data.get("storage_usage"),
                latency=data.get("latency"),
                process_count=data.get("process_count"),
                temperature=data.get("temperature"),
                threshold=getattr(self.config, f"alert_{rule['type'].split('_')[0]}_threshold", 0),
            )
            
            alert = {
                "type": rule["type"],
                "level": rule["level"],
                "message": rule["message"],
                "details": details,
                "timestamp": datetime.now().isoformat(),
                "data": {k: v for k, v in data.items() if k != "timestamp"},
            }
            
            # 记录报警历史
            self.alert_history.append(alert)
            
            # 限制历史记录大小
            if len(self.alert_history) > 1000:
                self.alert_history = self.alert_history[-1000:]
            
            # 发送报警通知
            self._send_alert_notification(alert)
            
            return alert
            
        except Exception as e:
            self.logger.error(f"创建报警失败: {e}")
            return None
    
    def _is_suppressed(self, alert_type: str) -> bool:
        """检查报警是否被抑制"""
        if alert_type in self.suppressed_alerts:
            suppression_time = self.suppressed_alerts[alert_type]
            if datetime.now() - suppression_time < timedelta(minutes=5):  # 默认5分钟
                return True
            else:
                # 抑制时间已过，清理记录
                del self.suppressed_alerts[alert_type]
        
        return False
    
    def _suppress_alert(self, alert_type: str, minutes: int = 5):
        """抑制报警"""
        self.suppressed_alerts[alert_type] = datetime.now()
        
        # 清理过期的抑制记录
        expired_types = []
        for atype, time in self.suppressed_alerts.items():
            if datetime.now() - time > timedelta(minutes=minutes * 2):  # 两倍的抑制时间
                expired_types.append(atype)
        
        for atype in expired_types:
            del self.suppressed_alerts[atype]
    
    def _send_alert_notification(self, alert: Dict[str, Any]):
        """发送报警通知"""
        try:
            # 记录日志
            log_message = f"{alert['level'].upper()}: {alert['message']} - {alert['details']}"
            
            if alert["level"] == "critical":
                self.logger.error(log_message)
            else:
                self.logger.warning(log_message)
            
            # 发送Webhook通知
            if self.config.enable_webhook_alerts and self.config.webhook_url:
                self._send_webhook_notification(alert)
            
            # 发送邮件通知
            if self.config.enable_email_alerts and alert["level"] == "critical":
                self._send_email_notification(alert)
                
        except Exception as e:
            self.logger.error(f"发送报警通知失败: {e}")
    
    def _send_webhook_notification(self, alert: Dict[str, Any]):
        """发送Webhook通知"""
        try:
            import requests
            
            payload = {
                "timestamp": alert["timestamp"],
                "level": alert["level"],
                "type": alert["type"],
                "message": alert["message"],
                "details": alert["details"],
                "source": "TV_Monitor",
                "tv_ip": self.config.tv_ip,
            }
            
            response = requests.post(
                self.config.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code != 200:
                self.logger.warning(f"Webhook通知失败: {response.status_code}")
                
        except Exception as e:
            self.logger.debug(f"Webhook通知异常: {e}")
    
    def _send_email_notification(self, alert: Dict[str, Any]):
        """发送邮件通知"""
        # 这里需要配置邮件服务器
        # 暂时只记录日志
        self.logger.info(f"邮件通知: {alert['message']} - {alert['details']}")
    
    def get_alert_summary(self, hours: int = 24) -> Dict[str, Any]:
        """获取报警摘要"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_alerts = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert["timestamp"].replace('Z', '+00:00')) > cutoff_time
        ]
        
        # 按级别统计
        level_counts = {}
        type_counts = {}
        
        for alert in recent_alerts:
            level = alert["level"]
            alert_type = alert["type"]
            
            level_counts[level] = level_counts.get(level, 0) + 1
            type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
        
        # 最近报警
        recent_alerts_sorted = sorted(
            recent_alerts,
            key=lambda x: x["timestamp"],
            reverse=True
        )[:10]  # 最近10条
        
        summary = {
            "period_hours": hours,
            "total_alerts": len(recent_alerts),
            "level_counts": level_counts,
            "type_counts": type_counts,
            "recent_alerts": recent_alerts_sorted,
            "suppressed_alerts": list(self.suppressed_alerts.keys()),
        }
        
        return summary
    
    def clear_alerts(self, older_than_hours: int = 24):
        """清理旧报警"""
        if older_than_hours <= 0:
            self.alert_history.clear()
            self.logger.info("已清除所有报警历史")
            return
        
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        
        initial_count = len(self.alert_history)
        self.alert_history = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert["timestamp"].replace('Z', '+00:00')) > cutoff_time
        ]
        
        cleared_count = initial_count - len(self.alert_history)
        self.logger.info(f"已清除 {cleared_count} 条报警历史（{older_than_hours}小时前）")
    
    def add_custom_alert_rule(self, rule: Dict[str, Any]):
        """添加自定义报警规则"""
        required_fields = ["type", "condition", "level", "message"]
        
        for field in required_fields:
            if field not in rule:
                raise ValueError(f"报警规则缺少必填字段: {field}")
        
        # 检查类型是否已存在
        for existing_rule in self.alert_rules:
            if existing_rule["type"] == rule["type"]:
                raise ValueError(f"报警规则类型已存在: {rule['type']}")
        
        # 设置默认值
        rule.setdefault("details_template", "")
        rule.setdefault("suppression_minutes", 5)
        
        self.alert_rules.append(rule)
        self.logger.info(f"已添加自定义报警规则: {rule['type']}")
    
    def remove_alert_rule(self, rule_type: str):
        """移除报警规则"""
        initial_count = len(self.alert_rules)
        self.alert_rules = [rule for rule in self.alert_rules if rule["type"] != rule_type]
        
        removed_count = initial_count - len(self.alert_rules)
        if removed_count > 0:
            self.logger.info(f"已移除报警规则: {rule_type}")
        else:
            self.logger.warning(f"未找到报警规则: {rule_type}")