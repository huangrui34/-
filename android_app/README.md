# Meeting TV Launcher

会议室小米电视专用安卓桌面及远程管理系统。

## 功能特性

- 🎯 **开机自启动** - 自动启动指定APP或切换HDMI信号源
- 📡 **设备管理** - 后台批量管理多台电视机
- 🔄 **远程控制** - 实时查看电视画面并远程操控
- 📦 **APK管理** - 后台一键安装/卸载电视应用
- 📝 **策略下发** - 后台配置策略并批量推送到设备
- 📸 **远程截屏** - 后台实时查看电视画面
- 🔒 **企业WiFi** - 支持802.1X/EAP企业级无线网络

## 项目结构

```
mi-tv-launcher/
├── tv-launcher-app/          # Android TV桌面应用
│   ├── app/src/main/java/    # Kotlin源码
│   └── ...
├── backend/                   # FastAPI后端服务
│   ├── app/                  # 后端应用
│   │   ├── main.py          # 主入口
│   │   ├── models.py        # 数据模型
│   │   └── templates/       # 前端页面
│   └── ...
├── 启动后台服务.bat          # 一键启动脚本
└── 创建快捷方式.ps1         # 桌面快捷方式创建脚本
```

## 快速启动

### 1. 启动后端服务

双击运行 `启动后台服务.bat`

或者手动启动：
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. 访问后台

打开浏览器访问: http://localhost:8000

## 电视端安装

通过ADB安装APK：
```bash
adb install app-debug.apk
```

## ADB远程连接

```bash
adb connect <电视IP地址>:5555
```

## 环境要求

- Python 3.9+
- Java JDK 11+
- Android SDK
- 小米电视 (Android 6.0+)
