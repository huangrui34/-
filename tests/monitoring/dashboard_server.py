"""
仪表板服务器
提供实时监控数据的Web界面
"""
import json
import logging
import threading
import time
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from .monitor_config import MonitorConfig

class DashboardServer:
    """仪表板服务器"""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.logger = logging.getLogger("DashboardServer")
        
        # 服务器状态
        self.is_running = False
        self.server_thread: Optional[threading.Thread] = None
        
        # 数据存储
        self.current_data: Dict[str, Any] = {}
        self.historical_data: Dict[str, list] = {
            "performance": [],
            "network": [],
            "alerts": [],
        }
        
        # HTML模板
        self.html_template = self._load_html_template()
    
    def _load_html_template(self) -> str:
        """加载HTML模板"""
        template = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>电视机监控仪表板</title>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                }
                
                .dashboard {
                    max-width: 1400px;
                    margin: 0 auto;
                }
                
                .header {
                    background: rgba(255, 255, 255, 0.95);
                    border-radius: 15px;
                    padding: 25px;
                    margin-bottom: 25px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                
                .header h1 {
                    color: #333;
                    font-size: 28px;
                    font-weight: 600;
                }
                
                .header .status {
                    display: flex;
                    align-items: center;
                    gap: 15px;
                }
                
                .status-indicator {
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    background: #4CAF50;
                    animation: pulse 2s infinite;
                }
                
                .status-indicator.offline {
                    background: #f44336;
                }
                
                @keyframes pulse {
                    0% { opacity: 1; }
                    50% { opacity: 0.5; }
                    100% { opacity: 1; }
                }
                
                .grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                    gap: 25px;
                }
                
                .card {
                    background: rgba(255, 255, 255, 0.95);
                    border-radius: 15px;
                    padding: 25px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                    transition: transform 0.3s ease;
                }
                
                .card:hover {
                    transform: translateY(-5px);
                }
                
                .card-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 20px;
                    padding-bottom: 15px;
                    border-bottom: 2px solid #f0f0f0;
                }
                
                .card-title {
                    color: #333;
                    font-size: 20px;
                    font-weight: 600;
                }
                
                .card-icon {
                    width: 40px;
                    height: 40px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 10px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-size: 20px;
                }
                
                .metric {
                    margin: 15px 0;
                }
                
                .metric-label {
                    color: #666;
                    font-size: 14px;
                    margin-bottom: 5px;
                    display: flex;
                    justify-content: space-between;
                }
                
                .metric-value {
                    color: #333;
                    font-size: 24px;
                    font-weight: 600;
                }
                
                .progress-bar {
                    height: 8px;
                    background: #f0f0f0;
                    border-radius: 4px;
                    overflow: hidden;
                    margin-top: 10px;
                }
                
                .progress-fill {
                    height: 100%;
                    background: linear-gradient(90deg, #4CAF50, #8BC34A);
                    border-radius: 4px;
                    transition: width 1s ease;
                }
                
                .progress-fill.warning {
                    background: linear-gradient(90deg, #FF9800, #FFC107);
                }
                
                .progress-fill.danger {
                    background: linear-gradient(90deg, #f44336, #FF5252);
                }
                
                .alert-list {
                    max-height: 300px;
                    overflow-y: auto;
                }
                
                .alert-item {
                    padding: 15px;
                    margin: 10px 0;
                    background: #f8f9fa;
                    border-radius: 10px;
                    border-left: 4px solid #4CAF50;
                }
                
                .alert-item.warning {
                    border-left-color: #FF9800;
                }
                
                .alert-item.critical {
                    border-left-color: #f44336;
                }
                
                .alert-time {
                    color: #666;
                    font-size: 12px;
                    margin-bottom: 5px;
                }
                
                .alert-message {
                    color: #333;
                    font-weight: 500;
                }
                
                .screenshot-container {
                    text-align: center;
                }
                
                .screenshot {
                    max-width: 100%;
                    border-radius: 10px;
                    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
                }
                
                .refresh-info {
                    text-align: center;
                    color: #666;
                    font-size: 12px;
                    margin-top: 20px;
                }
                
                .last-updated {
                    color: #666;
                    font-size: 12px;
                    margin-top: 10px;
                    text-align: center;
                }
                
                @media (max-width: 768px) {
                    .grid {
                        grid-template-columns: 1fr;
                    }
                    
                    .header {
                        flex-direction: column;
                        gap: 15px;
                        text-align: center;
                    }
                }
            </style>
            <script>
                let lastUpdate = new Date();
                
                function updateTime() {
                    const now = new Date();
                    const elapsed = Math.floor((now - lastUpdate) / 1000);
                    document.getElementById('lastUpdated').textContent = 
                        `最后更新: ${elapsed}秒前`;
                }
                
                function updateDashboard() {
                    fetch('/api/data')
                        .then(response => response.json())
                        .then(data => {
                            updateMetrics(data);
                            lastUpdate = new Date();
                        })
                        .catch(error => {
                            console.error('更新数据失败:', error);
                        });
                }
                
                function updateMetrics(data) {
                    // 更新性能指标
                    if (data.performance) {
                        updateMetric('cpuUsage', data.performance.cpu_usage, '%', 80);
                        updateMetric('memoryUsage', data.performance.memory_usage, '%', 85);
                        updateMetric('storageUsage', data.performance.storage_usage, '%', 90);
                        updateMetric('processCount', data.performance.process_count, '个');
                        updateMetric('temperature', data.performance.temperature, '°C', 60);
                    }
                    
                    // 更新网络指标
                    if (data.network) {
                        updateMetric('latency', data.network.latency, 'ms', 200);
                        updateMetric('connected', data.network.connected ? '在线' : '离线');
                    }
                    
                    // 更新截图
                    if (data.screenshot) {
                        const img = document.getElementById('screenshot');
                        if (img && data.screenshot.url) {
                            img.src = data.screenshot.url + '?t=' + new Date().getTime();
                            img.style.display = 'block';
                        }
                    }
                    
                    // 更新报警列表
                    if (data.alerts && data.alerts.length > 0) {
                        const alertList = document.getElementById('alertList');
                        alertList.innerHTML = '';
                        
                        data.alerts.slice(0, 5).forEach(alert => {
                            const alertItem = document.createElement('div');
                            alertItem.className = `alert-item ${alert.level}`;
                            alertItem.innerHTML = `
                                <div class="alert-time">${new Date(alert.timestamp).toLocaleString()}</div>
                                <div class="alert-message">${alert.message}</div>
                                ${alert.details ? `<div class="alert-details" style="font-size:12px;color:#666;margin-top:5px;">${alert.details}</div>` : ''}
                            `;
                            alertList.appendChild(alertItem);
                        });
                    }
                    
                    // 更新状态指示器
                    const indicator = document.getElementById('statusIndicator');
                    if (data.network && data.network.connected) {
                        indicator.className = 'status-indicator';
                        indicator.title = '在线';
                    } else {
                        indicator.className = 'status-indicator offline';
                        indicator.title = '离线';
                    }
                }
                
                function updateMetric(elementId, value, unit = '', warningThreshold = null) {
                    const element = document.getElementById(elementId);
                    if (!element) return;
                    
                    const valueElement = element.querySelector('.metric-value');
                    const progressElement = element.querySelector('.progress-fill');
                    
                    if (valueElement) {
                        valueElement.textContent = value !== null && value !== undefined ? 
                            `${value} ${unit}` : '--';
                    }
                    
                    if (progressElement && warningThreshold && value !== null && value !== undefined) {
                        const percentage = Math.min(100, (value / warningThreshold) * 100);
                        progressElement.style.width = `${percentage}%`;
                        
                        // 根据阈值设置颜色
                        if (value > warningThreshold) {
                            progressElement.className = 'progress-fill danger';
                        } else if (value > warningThreshold * 0.8) {
                            progressElement.className = 'progress-fill warning';
                        } else {
                            progressElement.className = 'progress-fill';
                        }
                    }
                }
                
                // 页面加载时初始化
                document.addEventListener('DOMContentLoaded', function() {
                    // 初始加载数据
                    updateDashboard();
                    
                    // 设置自动刷新
                    setInterval(updateDashboard, 5000); // 5秒刷新一次
                    setInterval(updateTime, 1000); // 1秒更新时间
                    
                    // 手动刷新按钮
                    document.getElementById('refreshBtn').addEventListener('click', updateDashboard);
                });
            </script>
        </head>
        <body>
            <div class="dashboard">
                <div class="header">
                    <div>
                        <h1>📺 电视机监控仪表板</h1>
                        <div style="color:#666;margin-top:5px;">
                            电视机IP: {{tv_ip}} | 开始时间: {{start_time}}
                        </div>
                    </div>
                    <div class="status">
                        <div id="statusIndicator" class="status-indicator" title="在线"></div>
                        <span style="color:#333;font-weight:500;">监控运行中</span>
                        <button id="refreshBtn" style="
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 8px;
                            cursor: pointer;
                            font-weight: 500;
                        ">刷新数据</button>
                    </div>
                </div>
                
                <div class="grid">
                    <!-- 性能监控卡片 -->
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">📊 性能监控</div>
                            <div class="card-icon">⚡</div>
                        </div>
                        
                        <div class="metric" id="cpuUsage">
                            <div class="metric-label">
                                <span>CPU使用率</span>
                                <span id="cpuUsageLabel"></span>
                            </div>
                            <div class="metric-value">--</div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: 0%"></div>
                            </div>
                        </div>
                        
                        <div class="metric" id="memoryUsage">
                            <div class="metric-label">
                                <span>内存使用率</span>
                                <span id="memoryUsageLabel"></span>
                            </div>
                            <div class="metric-value">--</div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: 0%"></div>
                            </div>
                        </div>
                        
                        <div class="metric" id="storageUsage">
                            <div class="metric-label">
                                <span>存储使用率</span>
                                <span id="storageUsageLabel"></span>
                            </div>
                            <div class="metric-value">--</div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: 0%"></div>
                            </div>
                        </div>
                        
                        <div class="metric" id="processCount">
                            <div class="metric-label">
                                <span>进程数量</span>
                                <span id="processCountLabel"></span>
                            </div>
                            <div class="metric-value">--</div>
                        </div>
                        
                        <div class="metric" id="temperature">
                            <div class="metric-label">
                                <span>温度</span>
                                <span id="temperatureLabel"></span>
                            </div>
                            <div class="metric-value">--</div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: 0%"></div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 网络监控卡片 -->
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">🌐 网络监控</div>
                            <div class="card-icon">📶</div>
                        </div>
                        
                        <div class="metric" id="connected">
                            <div class="metric-label">
                                <span>连接状态</span>
                            </div>
                            <div class="metric-value">--</div>
                        </div>
                        
                        <div class="metric" id="latency">
                            <div class="metric-label">
                                <span>网络延迟</span>
                                <span id="latencyLabel"></span>
                            </div>
                            <div class="metric-value">--</div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: 0%"></div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 报警监控卡片 -->
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">🚨 实时报警</div>
                            <div class="card-icon">⚠️</div>
                        </div>
                        
                        <div class="alert-list" id="alertList">
                            <div style="text-align:center;color:#666;padding:40px 20px;">
                                暂无报警信息
                            </div>
                        </div>
                    </div>
                    
                    <!-- 屏幕监控卡片 -->
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">📸 屏幕监控</div>
                            <div class="card-icon">🖥️</div>
                        </div>
                        
                        <div class="screenshot-container">
                            <img id="screenshot" class="screenshot" 
                                 style="display:none;max-height:300px;"
                                 alt="电视机屏幕截图">
                            <div id="noScreenshot" style="text-align:center;color:#666;padding:40px 20px;">
                                等待截图...
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="refresh-info">
                    数据每5秒自动刷新 | 
                    <span id="lastUpdated">最后更新: --</span>
                </div>
            </div>
        </body>
        </html>
        """
        return template
    
    def start(self) -> bool:
        """启动仪表板服务器"""
        if self.is_running:
            self.logger.warning("仪表板服务器已在运行中")
            return False
        
        try:
            self.logger.info(f"正在启动仪表板服务器，端口: {self.config.dashboard_port}")
            
            self.is_running = True
            self.server_thread = threading.Thread(
                target=self._run_server,
                name="DashboardServer",
                daemon=True
            )
            self.server_thread.start()
            
            self.logger.info(f"仪表板服务器已启动: http://localhost:{self.config.dashboard_port}")
            return True
            
        except Exception as e:
            self.logger.error(f"启动仪表板服务器失败: {e}")
            self.is_running = False
            return False
    
    def stop(self):
        """停止仪表板服务器"""
        self.is_running = False
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
        
        self.logger.info("仪表板服务器已停止")
    
    def _run_server(self):
        """运行HTTP服务器"""
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            import urllib.parse
            
            class DashboardHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    # 解析请求路径
                    parsed_path = urllib.parse.urlparse(self.path)
                    path = parsed_path.path
                    
                    # API端点
                    if path == '/api/data':
                        self._handle_api_data()
                    elif path == '/api/status':
                        self._handle_api_status()
                    elif path == '/api/screenshot':
                        self._handle_api_screenshot()
                    elif path == '/api/alerts':
                        self._handle_api_alerts()
                    else:
                        # 默认返回仪表板页面
                        self._handle_dashboard()
                
                def _handle_dashboard(self):
                    """处理仪表板页面请求"""
                    try:
                        # 渲染HTML模板
                        html = self.server.dashboard_server.html_template
                        
                        # 替换模板变量
                        html = html.replace('{{tv_ip}}', self.server.dashboard_server.config.tv_ip)
                        html = html.replace('{{start_time}}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(html.encode('utf-8'))
                        
                    except Exception as e:
                        self.send_error(500, f"渲染仪表板失败: {str(e)}")
                
                def _handle_api_data(self):
                    """处理API数据请求"""
                    try:
                        data = self.server.dashboard_server._prepare_api_data()
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
                        
                    except Exception as e:
                        self.send_error(500, f"获取API数据失败: {str(e)}")
                
                def _handle_api_status(self):
                    """处理API状态请求"""
                    try:
                        status = {
                            'status': 'running',
                            'timestamp': datetime.now().isoformat(),
                            'tv_ip': self.server.dashboard_server.config.tv_ip,
                            'uptime': 'TODO',  # 需要实现运行时间计算
                        }
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(status, ensure_ascii=False).encode('utf-8'))
                        
                    except Exception as e:
                        self.send_error(500, f"获取状态失败: {str(e)}")
                
                def _handle_api_screenshot(self):
                    """处理API截图请求"""
                    try:
                        # 获取最新截图
                        screenshot_data = self.server.dashboard_server._get_latest_screenshot_data()
                        
                        if screenshot_data and 'url' in screenshot_data:
                            # 重定向到截图URL
                            self.send_response(302)
                            self.send_header('Location', screenshot_data['url'])
                            self.end_headers()
                        else:
                            self.send_response(404)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({'error': 'No screenshot available'}).encode('utf-8'))
                            
                    except Exception as e:
                        self.send_error(500, f"获取截图失败: {str(e)}")
                
                def _handle_api_alerts(self):
                    """处理API报警请求"""
                    try:
                        alerts = self.server.dashboard_server._get_recent_alerts()
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(alerts, ensure_ascii=False).encode('utf-8'))
                        
                    except Exception as e:
                        self.send_error(500, f"获取报警失败: {str(e)}")
                
                def log_message(self, format, *args):
                    """重写日志方法，避免过多日志输出"""
                    # 只记录错误
                    if args and 'error' in args[0].lower():
                        super().log_message(format, *args)
            
            # 创建HTTP服务器
            server_address = ('', self.config.dashboard_port)
            httpd = HTTPServer(server_address, DashboardHandler)
            
            # 传递dashboard_server实例
            httpd.dashboard_server = self
            
            self.logger.info(f"仪表板服务器监听端口: {self.config.dashboard_port}")
            
            # 运行服务器
            while self.is_running:
                httpd.handle_request()
                time.sleep(0.1)  # 短暂延迟，避免CPU占用过高
                
        except Exception as e:
            self.logger.error(f"仪表板服务器运行异常: {e}")
            self.is_running = False
    
    def update_data(self, monitoring_data: Dict[str, Any]):
        """更新监控数据"""
        self.current_data = monitoring_data.copy()
        
        # 保存历史数据
        if 'performance_metrics' in monitoring_data and monitoring_data['performance_metrics']:
            latest_perf = monitoring_data['performance_metrics'][-1] if monitoring_data['performance_metrics'] else {}
            if latest_perf:
                self.historical_data['performance'].append(latest_perf)
                
                # 限制历史数据大小
                if len(self.historical_data['performance']) > 100:
                    self.historical_data['performance'] = self.historical_data['performance'][-100:]
        
        if 'network_stats' in monitoring_data and monitoring_data['network_stats']:
            latest_network = monitoring_data['network_stats'][-1] if monitoring_data['network_stats'] else {}
            if latest_network:
                self.historical_data['network'].append(latest_network)
                
                if len(self.historical_data['network']) > 100:
                    self.historical_data['network'] = self.historical_data['network'][-100:]
        
        if 'alerts' in monitoring_data and monitoring_data['alerts']:
            latest_alerts = monitoring_data['alerts'][-5:] if monitoring_data['alerts'] else []  # 只保存最近5个
            self.historical_data['alerts'].extend(latest_alerts)
            
            if len(self.historical_data['alerts']) > 50:
                self.historical_data['alerts'] = self.historical_data['alerts'][-50:]
    
    def _prepare_api_data(self) -> Dict[str, Any]:
        """准备API数据"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'performance': {},
            'network': {},
            'screenshot': {},
            'alerts': [],
        }
        
        # 性能数据
        if self.historical_data['performance']:
            latest_perf = self.historical_data['performance'][-1]
            data['performance'] = {
                'cpu_usage': latest_perf.get('cpu_usage'),
                'memory_usage': latest_perf.get('memory_usage'),
                'storage_usage': latest_perf.get('storage_usage'),
                'process_count': latest_perf.get('process_count'),
                'temperature': latest_perf.get('temperature'),
            }
        
        # 网络数据
        if self.historical_data['network']:
            latest_network = self.historical_data['network'][-1]
            data['network'] = {
                'connected': latest_network.get('connected', False),
                'latency': latest_network.get('latency'),
                'packet_loss': latest_network.get('packet_loss'),
            }
        
        # 截图数据
        screenshot_data = self._get_latest_screenshot_data()
        if screenshot_data:
            data['screenshot'] = screenshot_data
        
        # 报警数据
        if self.historical_data['alerts']:
            data['alerts'] = self.historical_data['alerts'][-10:]  # 最近10个报警
        
        return data
    
    def _get_latest_screenshot_data(self) -> Dict[str, Any]:
        """获取最新截图数据"""
        try:
            # 查找最新的截图文件
            screenshot_dir = self.config.get_directories()["screenshots"]
            screenshot_files = list(screenshot_dir.glob("screenshot_*.png"))
            
            if not screenshot_files:
                return {}
            
            # 按修改时间排序，获取最新的
            screenshot_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            latest_file = screenshot_files[0]
            
            # 构建URL（假设服务器可以访问文件）
            # 在实际部署中，需要配置静态文件服务
            return {
                'filepath': str(latest_file),
                'filename': latest_file.name,
                'url': f'/static/screenshots/{latest_file.name}',
                'timestamp': datetime.fromtimestamp(latest_file.stat().st_mtime).isoformat(),
                'size': latest_file.stat().st_size,
            }
            
        except Exception as e:
            self.logger.debug(f"获取最新截图失败: {e}")
            return {}
    
    def _get_recent_alerts(self) -> List[Dict[str, Any]]:
        """获取最近报警"""
        if self.historical_data['alerts']:
            return self.historical_data['alerts'][-20:]  # 最近20个报警
        return []
    
    def get_server_status(self) -> Dict[str, Any]:
        """获取服务器状态"""
        return {
            'is_running': self.is_running,
            'port': self.config.dashboard_port,
            'tv_ip': self.config.tv_ip,
            'data_counts': {
                'performance': len(self.historical_data['performance']),
                'network': len(self.historical_data['network']),
                'alerts': len(self.historical_data['alerts']),
            },
            'current_time': datetime.now().isoformat(),
        }