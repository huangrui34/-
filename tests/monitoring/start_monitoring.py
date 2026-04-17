#!/usr/bin/env python3
"""
监控系统启动脚本
启动远程调试监控环境，实时查看电视机状态
"""
import os
import sys
import time
import signal
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "tests" / "monitoring"))

from monitor_config import TEST_CONFIG, MonitorConfig
from monitor_manager import MonitorManager

def signal_handler(sig, frame):
    """处理信号"""
    print("\n接收到停止信号，正在关闭监控...")
    sys.exit(0)

def setup_monitoring(config: MonitorConfig) -> MonitorManager:
    """设置监控系统"""
    print("="*60)
    print("电视机远程调试监控系统")
    print("="*60)
    print(f"电视机IP: {config.tv_ip}:{config.tv_port}")
    print(f"数据目录: {config.data_directory}")
    print(f"仪表板端口: {config.dashboard_port}")
    print("="*60)
    
    # 创建监控管理器
    manager = MonitorManager(config)
    
    # 初始化监控组件
    print("正在初始化监控组件...")
    if not manager.initialize():
        print("❌ 监控系统初始化失败")
        sys.exit(1)
    
    print("✅ 监控系统初始化完成")
    return manager

def run_monitoring(manager: MonitorManager):
    """运行监控系统"""
    print("\n正在启动监控系统...")
    
    # 启动监控
    if not manager.start():
        print("❌ 监控系统启动失败")
        sys.exit(1)
    
    print("✅ 监控系统已启动")
    print(f"📊 仪表板地址: http://localhost:{manager.config.dashboard_port}")
    
    # 显示状态信息
    print("\n监控状态:")
    print("-"*40)
    
    try:
        while True:
            status = manager.get_status()
            latest_data = manager.get_latest_data()
            
            # 清屏（可选）
            if os.name == 'nt':  # Windows
                os.system('cls')
            else:  # Linux/Mac
                os.system('clear')
            
            # 显示标题
            print("="*60)
            print("电视机远程调试监控系统 - 实时状态")
            print("="*60)
            print(f"电视机: {manager.config.tv_ip}:{manager.config.tv_port}")
            print(f"运行时间: {status.get('uptime', 'N/A')}")
            print(f"监控状态: {'✅ 运行中' if status['is_running'] else '❌ 已停止'}")
            print("="*60)
            
            # 显示组件状态
            print("\n📊 监控组件状态:")
            components = status.get('components', {})
            for name, enabled in components.items():
                status_icon = "✅" if enabled else "❌"
                print(f"  {status_icon} {name.replace('_', ' ').title()}")
            
            # 显示数据统计
            print("\n📈 数据统计:")
            data_counts = status.get('data_counts', {})
            for name, count in data_counts.items():
                print(f"  📊 {name.replace('_', ' ').title()}: {count}")
            
            # 显示最新数据
            print("\n🔄 最新监控数据:")
            
            # 性能数据
            if 'last_performance' in latest_data:
                perf = latest_data['last_performance']
                print(f"  ⚡ CPU使用率: {perf.get('cpu_usage', 'N/A')}%")
                print(f"  💾 内存使用率: {perf.get('memory_usage', 'N/A')}%")
                print(f"  💿 存储使用率: {perf.get('storage_usage', 'N/A')}%")
                print(f"  🔢 进程数量: {perf.get('process_count', 'N/A')}")
                if perf.get('temperature'):
                    print(f"  🌡️  温度: {perf.get('temperature')}°C")
            
            # 网络数据
            if 'last_network' in latest_data:
                network = latest_data['last_network']
                status_icon = "✅" if network.get('connected') else "❌"
                print(f"  🌐 网络状态: {status_icon} {'在线' if network.get('connected') else '离线'}")
                if network.get('latency'):
                    print(f"  ⏱️  网络延迟: {network.get('latency')}ms")
            
            # 最新报警
            if 'last_alert' in latest_data:
                alert = latest_data['last_alert']
                alert_icon = "🚨" if alert.get('level') == 'critical' else "⚠️"
                print(f"\n{alert_icon} 最新报警:")
                print(f"  类型: {alert.get('type', 'N/A')}")
                print(f"  级别: {alert.get('level', 'N/A')}")
                print(f"  消息: {alert.get('message', 'N/A')}")
                print(f"  时间: {alert.get('timestamp', 'N/A')}")
            
            # 显示控制指令
            print("\n" + "="*60)
            print("控制指令:")
            print("  • 按 Ctrl+C 停止监控")
            print("  • 打开浏览器访问仪表板查看详细信息")
            print("="*60)
            
            # 等待一段时间后刷新
            time.sleep(manager.config.dashboard_refresh_interval)
            
    except KeyboardInterrupt:
        print("\n\n正在停止监控系统...")
    finally:
        # 停止监控
        manager.stop()
        print("✅ 监控系统已停止")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="电视机远程调试监控系统")
    parser.add_argument("--tv-ip", default="10.181.184.226", help="电视机IP地址")
    parser.add_argument("--tv-port", type=int, default=5555, help="电视机ADB端口")
    parser.add_argument("--dashboard-port", type=int, default=8080, help="仪表板端口")
    parser.add_argument("--data-dir", default="monitoring_data", help="数据存储目录")
    parser.add_argument("--config", help="配置文件路径")
    
    args = parser.parse_args()
    
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 加载配置
    if args.config:
        config = MonitorConfig.load(args.config)
        print(f"已加载配置文件: {args.config}")
    else:
        # 使用命令行参数创建配置
        config = MonitorConfig(
            tv_ip=args.tv_ip,
            tv_port=args.tv_port,
            data_directory=args.data_dir,
            dashboard_port=args.dashboard_port,
        )
    
    # 验证配置
    errors = config.validate()
    if errors:
        print("❌ 配置错误:")
        for error in errors:
            print(f"  • {error}")
        sys.exit(1)
    
    try:
        # 设置监控系统
        manager = setup_monitoring(config)
        
        # 运行监控系统
        run_monitoring(manager)
        
    except Exception as e:
        print(f"❌ 监控系统运行异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()