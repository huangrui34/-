"""
监控管理器
协调各种监控任务，提供统一的监控接口
"""
import time
import threading
import logging
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime, timedelta
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, Future

from .monitor_config import MonitorConfig
from .screen_monitor import ScreenMonitor
from .performance_monitor import PerformanceMonitor
from .log_monitor import LogMonitor
from .network_monitor import NetworkMonitor
from .alert_manager import AlertManager
from .dashboard_server import DashboardServer

class MonitorManager:
    """监控管理器"""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.logger = self._setup_logger()
        
        # 监控组件
        self.screen_monitor: Optional[ScreenMonitor] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None
        self.log_monitor: Optional[LogMonitor] = None
        self.network_monitor: Optional[NetworkMonitor] = None
        self.alert_manager: Optional[AlertManager] = None
        self.dashboard_server: Optional[DashboardServer] = None
        
        # 状态管理
        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.monitoring_thread: Optional[threading.Thread] = None
        
        # 任务队列
        self.task_queue = Queue()
        self.results_queue = Queue()
        
        # 线程池
        self.thread_pool = ThreadPoolExecutor(max_workers=5)
        
        # 监控数据存储
        self.monitoring_data: Dict[str, Any] = {
            "screen_shots": [],
            "performance_metrics": [],
            "network_stats": [],
            "alerts": [],
            "logs": [],
        }
        
        # 回调函数
        self.callbacks: Dict[str, List[Callable]] = {
            "on_screenshot": [],
            "on_performance_data": [],
            "on_network_stats": [],
            "on_alert": [],
            "on_error": [],
        }
        
        # 创建目录
        self.directories = config.get_directories()
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger("MonitorManager")
        logger.setLevel(getattr(logging, self.config.log_level))
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # 文件处理器
        if self.config.enable_log_collection:
            log_dir = Path(self.config.data_directory) / self.config.log_directory
            log_dir.mkdir(parents=True, exist_ok=True)
            
            log_file = log_dir / f"monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def initialize(self) -> bool:
        """初始化监控组件"""
        try:
            self.logger.info("正在初始化监控管理器...")
            
            # 初始化屏幕监控
            if self.config.enable_screen_monitoring:
                self.screen_monitor = ScreenMonitor(self.config)
                self.logger.info("屏幕监控已初始化")
            
            # 初始化性能监控
            if self.config.enable_performance_monitoring:
                self.performance_monitor = PerformanceMonitor(self.config)
                self.logger.info("性能监控已初始化")
            
            # 初始化日志监控
            if self.config.enable_log_collection:
                self.log_monitor = LogMonitor(self.config)
                self.logger.info("日志监控已初始化")
            
            # 初始化网络监控
            if self.config.enable_network_monitoring:
                self.network_monitor = NetworkMonitor(self.config)
                self.logger.info("网络监控已初始化")
            
            # 初始化报警管理器
            if self.config.enable_alerts:
                self.alert_manager = AlertManager(self.config)
                self.logger.info("报警管理器已初始化")
            
            # 初始化仪表板服务器
            if self.config.enable_live_dashboard:
                self.dashboard_server = DashboardServer(self.config)
                self.logger.info("仪表板服务器已初始化")
            
            self.logger.info("监控管理器初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"监控管理器初始化失败: {e}")
            return False
    
    def start(self) -> bool:
        """启动监控"""
        if self.is_running:
            self.logger.warning("监控已在运行中")
            return False
        
        try:
            self.logger.info("正在启动监控...")
            self.is_running = True
            self.start_time = datetime.now()
            
            # 启动监控线程
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                name="MonitoringLoop"
            )
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            
            # 启动仪表板服务器
            if self.dashboard_server:
                self.dashboard_server.start()
            
            self.logger.info(f"监控已启动，开始时间: {self.start_time}")
            return True
            
        except Exception as e:
            self.logger.error(f"启动监控失败: {e}")
            self.is_running = False
            return False
    
    def stop(self) -> bool:
        """停止监控"""
        if not self.is_running:
            self.logger.warning("监控未在运行")
            return False
        
        try:
            self.logger.info("正在停止监控...")
            self.is_running = False
            
            # 等待监控线程结束
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=10)
            
            # 停止仪表板服务器
            if self.dashboard_server:
                self.dashboard_server.stop()
            
            # 关闭线程池
            self.thread_pool.shutdown(wait=True)
            
            # 保存监控数据
            self._save_monitoring_data()
            
            duration = datetime.now() - self.start_time
            self.logger.info(f"监控已停止，运行时间: {duration}")
            return True
            
        except Exception as e:
            self.logger.error(f"停止监控失败: {e}")
            return False
    
    def _monitoring_loop(self):
        """监控主循环"""
        self.logger.info("监控主循环开始")
        
        # 初始化上次执行时间
        last_screen_time = time.time()
        last_performance_time = time.time()
        last_network_time = time.time()
        
        try:
            while self.is_running:
                current_time = time.time()
                
                # 执行屏幕监控
                if (self.screen_monitor and 
                    current_time - last_screen_time >= self.config.screenshot_interval):
                    self._execute_monitoring_task(
                        self.screen_monitor.capture_screenshot,
                        "screen_capture"
                    )
                    last_screen_time = current_time
                
                # 执行性能监控
                if (self.performance_monitor and 
                    current_time - last_performance_time >= self.config.performance_interval):
                    self._execute_monitoring_task(
                        self.performance_monitor.collect_metrics,
                        "performance_collection"
                    )
                    last_performance_time = current_time
                
                # 执行网络监控
                if (self.network_monitor and 
                    current_time - last_network_time >= self.config.ping_interval):
                    self._execute_monitoring_task(
                        self.network_monitor.check_network,
                        "network_check"
                    )
                    last_network_time = current_time
                
                # 处理任务结果
                self._process_results()
                
                # 短暂休眠，避免CPU占用过高
                time.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"监控循环异常: {e}")
            self._trigger_callbacks("on_error", {"error": str(e)})
        finally:
            self.logger.info("监控主循环结束")
    
    def _execute_monitoring_task(self, task_func: Callable, task_name: str):
        """执行监控任务"""
        try:
            future = self.thread_pool.submit(task_func)
            future.add_done_callback(
                lambda f: self._handle_task_result(f, task_name)
            )
        except Exception as e:
            self.logger.error(f"提交监控任务失败 {task_name}: {e}")
    
    def _handle_task_result(self, future: Future, task_name: str):
        """处理任务结果"""
        try:
            result = future.result(timeout=30)
            if result:
                self.results_queue.put((task_name, result))
        except Exception as e:
            self.logger.error(f"监控任务执行失败 {task_name}: {e}")
    
    def _process_results(self):
        """处理监控结果"""
        try:
            while True:
                try:
                    task_name, result = self.results_queue.get_nowait()
                    self._handle_monitoring_result(task_name, result)
                except Empty:
                    break
        except Exception as e:
            self.logger.error(f"处理监控结果失败: {e}")
    
    def _handle_monitoring_result(self, task_name: str, result: Dict[str, Any]):
        """处理监控结果"""
        try:
            if task_name == "screen_capture":
                self._handle_screenshot_result(result)
            elif task_name == "performance_collection":
                self._handle_performance_result(result)
            elif task_name == "network_check":
                self._handle_network_result(result)
            
            # 更新仪表板数据
            if self.dashboard_server:
                self.dashboard_server.update_data(self.monitoring_data)
                
        except Exception as e:
            self.logger.error(f"处理监控结果 {task_name} 失败: {e}")
    
    def _handle_screenshot_result(self, result: Dict[str, Any]):
        """处理截图结果"""
        screenshot_data = {
            "timestamp": datetime.now().isoformat(),
            "filepath": result.get("filepath"),
            "size": result.get("size"),
            "success": result.get("success", False),
        }
        
        self.monitoring_data["screen_shots"].append(screenshot_data)
        
        # 限制截图数量
        max_count = self.config.screenshot_max_count
        if len(self.monitoring_data["screen_shots"]) > max_count:
            self.monitoring_data["screen_shots"] = self.monitoring_data["screen_shots"][-max_count:]
        
        # 触发回调
        self._trigger_callbacks("on_screenshot", screenshot_data)
        
        # 记录日志
        if screenshot_data["success"]:
            self.logger.debug(f"截图成功: {screenshot_data['filepath']}")
        else:
            self.logger.warning("截图失败")
    
    def _handle_performance_result(self, result: Dict[str, Any]):
        """处理性能监控结果"""
        performance_data = {
            "timestamp": datetime.now().isoformat(),
            "cpu_usage": result.get("cpu_usage"),
            "memory_usage": result.get("memory_usage"),
            "storage_usage": result.get("storage_usage"),
            "process_count": result.get("process_count"),
        }
        
        self.monitoring_data["performance_metrics"].append(performance_data)
        
        # 触发回调
        self._trigger_callbacks("on_performance_data", performance_data)
        
        # 检查报警条件
        if self.alert_manager:
            alerts = self.alert_manager.check_performance_alerts(performance_data)
            if alerts:
                for alert in alerts:
                    self._handle_alert(alert)
        
        # 记录日志
        self.logger.debug(f"性能数据: CPU={performance_data.get('cpu_usage')}%, "
                         f"内存={performance_data.get('memory_usage')}%")
    
    def _handle_network_result(self, result: Dict[str, Any]):
        """处理网络监控结果"""
        network_data = {
            "timestamp": datetime.now().isoformat(),
            "latency": result.get("latency"),
            "packet_loss": result.get("packet_loss"),
            "connected": result.get("connected", False),
            "bandwidth": result.get("bandwidth"),
        }
        
        self.monitoring_data["network_stats"].append(network_data)
        
        # 触发回调
        self._trigger_callbacks("on_network_stats", network_data)
        
        # 检查报警条件
        if self.alert_manager:
            alerts = self.alert_manager.check_network_alerts(network_data)
            if alerts:
                for alert in alerts:
                    self._handle_alert(alert)
        
        # 记录日志
        if network_data["connected"]:
            self.logger.debug(f"网络状态: 延迟={network_data.get('latency')}ms, "
                           f"丢包率={network_data.get('packet_loss')}%")
        else:
            self.logger.warning("网络连接失败")
    
    def _handle_alert(self, alert: Dict[str, Any]):
        """处理报警"""
        alert_data = {
            "timestamp": datetime.now().isoformat(),
            "level": alert.get("level", "warning"),
            "type": alert.get("type"),
            "message": alert.get("message"),
            "details": alert.get("details"),
        }
        
        self.monitoring_data["alerts"].append(alert_data)
        
        # 触发回调
        self._trigger_callbacks("on_alert", alert_data)
        
        # 记录日志
        log_func = getattr(self.logger, alert_data["level"], self.logger.warning)
        log_func(f"报警: {alert_data['message']} - {alert_data.get('details')}")
    
    def _trigger_callbacks(self, callback_name: str, data: Dict[str, Any]):
        """触发回调函数"""
        if callback_name in self.callbacks:
            for callback in self.callbacks[callback_name]:
                try:
                    callback(data)
                except Exception as e:
                    self.logger.error(f"回调函数 {callback_name} 执行失败: {e}")
    
    def register_callback(self, callback_name: str, callback: Callable):
        """注册回调函数"""
        if callback_name in self.callbacks:
            self.callbacks[callback_name].append(callback)
        else:
            self.logger.warning(f"未知的回调类型: {callback_name}")
    
    def unregister_callback(self, callback_name: str, callback: Callable):
        """注销回调函数"""
        if callback_name in self.callbacks and callback in self.callbacks[callback_name]:
            self.callbacks[callback_name].remove(callback)
    
    def _save_monitoring_data(self):
        """保存监控数据"""
        try:
            data_file = self.directories["base"] / "monitoring_data.json"
            
            save_data = {
                "config": self.config.to_dict(),
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": datetime.now().isoformat(),
                "monitoring_data": self.monitoring_data,
            }
            
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"监控数据已保存到: {data_file}")
            
        except Exception as e:
            self.logger.error(f"保存监控数据失败: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        status = {
            "is_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime": str(datetime.now() - self.start_time) if self.start_time else None,
            "components": {
                "screen_monitor": self.screen_monitor is not None,
                "performance_monitor": self.performance_monitor is not None,
                "log_monitor": self.log_monitor is not None,
                "network_monitor": self.network_monitor is not None,
                "alert_manager": self.alert_manager is not None,
                "dashboard_server": self.dashboard_server is not None,
            },
            "data_counts": {
                "screen_shots": len(self.monitoring_data["screen_shots"]),
                "performance_metrics": len(self.monitoring_data["performance_metrics"]),
                "network_stats": len(self.monitoring_data["network_stats"]),
                "alerts": len(self.monitoring_data["alerts"]),
                "logs": len(self.monitoring_data["logs"]),
            },
        }
        
        return status
    
    def get_latest_data(self) -> Dict[str, Any]:
        """获取最新监控数据"""
        latest_data = {}
        
        if self.monitoring_data["screen_shots"]:
            latest_data["last_screenshot"] = self.monitoring_data["screen_shots"][-1]
        
        if self.monitoring_data["performance_metrics"]:
            latest_data["last_performance"] = self.monitoring_data["performance_metrics"][-1]
        
        if self.monitoring_data["network_stats"]:
            latest_data["last_network"] = self.monitoring_data["network_stats"][-1]
        
        if self.monitoring_data["alerts"]:
            latest_data["last_alert"] = self.monitoring_data["alerts"][-1]
        
        return latest_data
    
    def cleanup_old_data(self, days_to_keep: int = 7):
        """清理旧数据"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days_to_keep)
            
            # 清理截图文件
            screenshots_dir = self.directories["screenshots"]
            for file in screenshots_dir.iterdir():
                if file.is_file():
                    file_time = datetime.fromtimestamp(file.stat().st_mtime)
                    if file_time < cutoff_time:
                        file.unlink()
            
            # 清理日志文件
            logs_dir = self.directories["logs"]
            for file in logs_dir.iterdir():
                if file.is_file():
                    file_time = datetime.fromtimestamp(file.stat().st_mtime)
                    if file_time < cutoff_time:
                        file.unlink()
            
            self.logger.info(f"已清理 {days_to_keep} 天前的旧数据")
            
        except Exception as e:
            self.logger.error(f"清理旧数据失败: {e}")