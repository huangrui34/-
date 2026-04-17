"""
屏幕监控器
负责捕获电视机屏幕截图
"""
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from .monitor_config import MonitorConfig

class ScreenMonitor:
    """屏幕监控器"""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.logger = logging.getLogger("ScreenMonitor")
        self.screenshot_count = 0
        
        # 截图目录
        self.screenshot_dir = config.get_directories()["screenshots"]
    
    def capture_screenshot(self) -> Dict[str, Any]:
        """捕获屏幕截图"""
        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}_{self.screenshot_count:04d}.png"
            filepath = self.screenshot_dir / filename
            
            # 使用ADB命令截图
            import subprocess
            
            # 电视机上的临时文件路径
            temp_file = f"/sdcard/screenshot_temp_{timestamp}.png"
            
            # 执行截图命令
            cmd = [
                "adb", "-s", f"{self.config.tv_ip}:{self.config.tv_port}",
                "shell", "screencap", "-p", temp_file
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.screenshot_interval
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"截图命令失败: {result.stderr}",
                    "timestamp": datetime.now().isoformat()
                }
            
            # 将截图文件从电视机拉取到本地
            pull_cmd = [
                "adb", "-s", f"{self.config.tv_ip}:{self.config.tv_port}",
                "pull", temp_file, str(filepath)
            ]
            
            result = subprocess.run(
                pull_cmd,
                capture_output=True,
                text=True,
                timeout=self.config.screenshot_interval
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"拉取截图失败: {result.stderr}",
                    "timestamp": datetime.now().isoformat()
                }
            
            # 清理电视机上的临时文件
            cleanup_cmd = [
                "adb", "-s", f"{self.config.tv_ip}:{self.config.tv_port}",
                "shell", "rm", temp_file
            ]
            
            subprocess.run(
                cleanup_cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # 检查文件是否存在
            if not filepath.exists():
                return {
                    "success": False,
                    "error": "截图文件未创建",
                    "timestamp": datetime.now().isoformat()
                }
            
            # 获取文件信息
            file_size = filepath.stat().st_size
            
            self.screenshot_count += 1
            
            return {
                "success": True,
                "filepath": str(filepath),
                "size": file_size,
                "timestamp": datetime.now().isoformat(),
                "count": self.screenshot_count
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "截图命令超时",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"截图异常: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    def get_latest_screenshot(self) -> Optional[Path]:
        """获取最新截图文件"""
        try:
            screenshots = list(self.screenshot_dir.glob("screenshot_*.png"))
            if not screenshots:
                return None
            
            # 按修改时间排序，获取最新的
            screenshots.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            return screenshots[0]
        except Exception as e:
            self.logger.error(f"获取最新截图失败: {e}")
            return None
    
    def get_screenshot_count(self) -> int:
        """获取截图数量"""
        try:
            screenshots = list(self.screenshot_dir.glob("screenshot_*.png"))
            return len(screenshots)
        except Exception as e:
            self.logger.error(f"获取截图数量失败: {e}")
            return 0
    
    def cleanup_old_screenshots(self, max_count: Optional[int] = None):
        """清理旧截图"""
        try:
            if max_count is None:
                max_count = self.config.screenshot_max_count
            
            screenshots = list(self.screenshot_dir.glob("screenshot_*.png"))
            if len(screenshots) <= max_count:
                return
            
            # 按修改时间排序，保留最新的
            screenshots.sort(key=lambda x: x.stat().st_mtime)
            to_delete = screenshots[:len(screenshots) - max_count]
            
            deleted_count = 0
            for file in to_delete:
                try:
                    file.unlink()
                    deleted_count += 1
                except Exception as e:
                    self.logger.error(f"删除截图文件失败 {file}: {e}")
            
            self.logger.info(f"已清理 {deleted_count} 个旧截图文件")
            
        except Exception as e:
            self.logger.error(f"清理旧截图失败: {e}")