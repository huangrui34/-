# 小米电视会议室Launcher

一个专业的Android TV Launcher应用，专为会议室小米电视设计，支持自动启动、远程管理和实时控制。

## 功能特性

### 🚀 核心功能
- **开机自启动**：电视开机后自动启动指定应用或切换到指定HDMI接口
- **策略管理**：通过网页后台配置启动策略（应用或HDMI）
- **远程部署**：通过IP地址一键部署应用到电视
- **实时控制**：Scrcpy-like远程屏幕镜像和鼠标控制

### 🖥️ 管理后台
- **设备管理**：查看所有已注册电视设备
- **策略配置**：创建和管理启动策略
- **远程控制**：实时屏幕截图和鼠标控制
- **操作日志**：记录所有管理操作

### 📱 Android应用
- **自动注册**：设备首次启动自动注册到后台
- **心跳机制**：定期向后台发送状态信息
- **网络信息**：显示有线和无线MAC地址、IP地址
- **企业WiFi**：支持企业级无线网络认证

### 🔧 高级功能
- **HDMI切换**：支持多种小米电视型号的HDMI信号源切换
- **白屏保护**：防止策略无效导致的电视白屏闪烁
- **资源监控**：实时监控电视RAM和存储使用情况
- **OTA更新**：支持静默在线更新

## 系统架构

```
├── android_app/          # Android TV应用 (Kotlin)
│   ├── app/src/main/java/com/company/tvlauncher/
│   │   ├── MainActivity.kt      # 主界面
│   │   ├── BootReceiver.kt      # 开机启动接收器
│   │   ├── LauncherExecutor.kt  # 策略执行器
│   │   ├── PolicyStore.kt       # 策略存储
│   │   └── RemoteApi.kt         # 远程API客户端
│   └── build.gradle
│
├── backend_server/       # 管理后台 (FastAPI + SQLite)
│   ├── app/
│   │   ├── main.py       # 主应用和API
│   │   ├── models.py     # 数据库模型
│   │   ├── schemas.py    # Pydantic模式
│   │   └── templates/    # 网页模板
│   └── requirements.txt
│
└── 启动脚本/
    ├── 启动后台服务.bat      # Windows启动脚本
    └── start_server.ps1   # PowerShell启动脚本
```

## 快速开始

### 1. 启动后端服务

```bash
cd backend_server
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

或者使用Windows批处理文件：
```bash
启动后台服务.bat
```

### 2. 构建Android应用

```bash
cd android_app
./gradlew assembleDebug
```

生成的APK文件：`android_app/app/build/outputs/apk/debug/app-debug.apk`

### 3. 访问管理后台

打开浏览器访问：`http://localhost:8000`

### 4. 部署到电视

1. 确保电视和电脑在同一网络
2. 在管理后台输入电视IP地址
3. 点击"一键部署上线"
4. 电视将自动安装应用并注册到后台

## 配置说明

### 环境要求
- **Android TV**: Android 6.0+ (API 23+)
- **Python**: 3.8+
- **ADB**: Android Debug Bridge
- **网络**: 电视和服务器在同一局域网

### 端口配置
- **后端服务**: 8000
- **ADB连接**: 5555
- **WebSocket**: 8000 (实时屏幕流)

### 数据库
- 使用SQLite数据库，自动创建于`backend_server/app.db`
- 包含设备、策略、心跳和操作日志表

## 使用指南

### 设备注册
1. 首次启动应用时，设备会自动注册到后台
2. 注册信息包括：设备名称、序列号、MAC地址、IP地址
3. 设备通过心跳机制保持与后台的连接

### 策略配置
1. 在后台创建策略，选择模式（应用或HDMI）
2. 绑定策略到设备
3. 设备重启或策略更新时自动执行新策略

### 远程控制
1. 在设备列表点击"远程控制"
2. 开启实时屏幕流
3. 点击屏幕图像进行控制
4. 使用右侧按钮模拟遥控器操作

### HDMI切换
支持多种切换方法：
1. 小米电视系统Intent
2. Android TV标准Intent
3. ADB命令切换
4. 手动设置引导

## 故障排除

### 常见问题

#### 1. ADB连接失败
- 检查电视IP地址是否正确
- 确保电视已开启ADB调试
- 在电视上确认ADB授权

#### 2. 白屏闪烁
- 检查策略配置是否有效
- 确保目标应用已安装
- 应用会自动显示"暂无策略"保护提示

#### 3. HDMI切换无效
- 检查HDMI线缆连接
- 尝试不同的HDMI端口
- 查看电视型号支持的切换方法

#### 4. 实时屏幕流卡顿
- 降低刷新频率（默认500ms）
- 检查网络带宽
- 调整截图分辨率

### 日志查看
- **后端日志**: 控制台输出
- **操作日志**: 管理后台日志页面
- **设备日志**: 通过ADB查看 `adb logcat`

## 开发指南

### 项目结构
- **Android应用**: 使用Kotlin开发，支持Android 6.0+
- **后端服务**: 使用FastAPI框架，SQLite数据库
- **前端界面**: 使用原生HTML/CSS/JavaScript

### 扩展功能
1. **添加新的HDMI切换方法**: 修改`LauncherExecutor.kt`
2. **增加新的API端点**: 修改`backend_server/app/main.py`
3. **修改前端界面**: 编辑`backend_server/app/templates/index.html`

### 测试
运行综合测试：
```bash
cd backend_server
python test_scenarios.py
```

## 许可证

本项目采用MIT许可证。详见LICENSE文件。

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

如有问题或建议，请通过GitHub Issues提交。

---

**注意**: 本项目专为企业会议室环境设计，请确保遵守相关法律法规和公司政策使用。