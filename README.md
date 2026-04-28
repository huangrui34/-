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
    └── start_server.bat     # Windows一键启动脚本
```

## 快速开始

### 1. 启动后端服务（Windows）

双击 `backend_server/start_server.bat`，首次运行会自动：
- 检测合适的Python版本（3.9-3.13）
- 创建虚拟环境
- 使用国内镜像源安装依赖
- 清理端口并启动服务
- 自动打开浏览器访问管理后台

### 2. 手动启动（Linux/macOS）

```bash
cd backend_server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

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
- **Python**: 3.9-3.13（3.14+不支持pydantic预编译包）
- **ADB**: Android Debug Bridge（可选，用于远程部署和控制）
- **网络**: 电视和服务器在同一局域网

### 端口配置
- **后端服务**: 8000
- **ADB连接**: 5555
- **WebSocket**: 8000 (实时屏幕流)

### 数据库
- 使用SQLite数据库，自动创建于`backend_server/tv_launcher.db`
- 首次启动自动创建表结构，无需手动初始化

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

#### 方式一：传统截图控制（基础功能）
1. 在设备列表点击"远程控制"
2. 点击"刷新截图"获取当前屏幕
3. 点击屏幕图像进行控制
4. 使用遥控器按钮模拟操作

#### 方式二：Scrcpy高级控制（推荐）
**Scrcpy是一个开源的Android屏幕镜像工具，提供真正的实时控制和低延迟体验。**

##### 安装Scrcpy
1. 下载Scrcpy: https://github.com/Genymobile/scrcpy/releases
2. 解压到任意目录（如 `C:\scrcpy`）
3. 确保ADB已安装（通常包含在Scrcpy包中）

##### 电视端设置
1. 进入电视设置 → 关于本机
2. 连续点击"版本号"7次开启开发者模式
3. 返回设置 → 开发者选项
4. 开启"USB调试"和"无线调试"

##### 使用步骤
1. 在管理后台点击"远程控制"
2. 点击"检查Scrcpy"验证安装
3. 点击"连接ADB"建立连接
4. 点击"启动Scrcpy"开始实时控制
5. 或者点击"获取命令"手动执行Scrcpy

##### Scrcpy高级功能
- **实时屏幕镜像**：真正的低延迟画面传输
- **鼠标控制**：直接点击电视屏幕
- **键盘输入**：支持文本输入
- **屏幕录制**：录制电视操作视频
- **音频传输**：Android 11+支持音频
- **多设备支持**：同时控制多台电视

##### 手动启动命令
```bash
scrcpy --serial 192.168.1.100:5555 --no-audio --max-fps 30 --bit-rate 2M --max-size 1024
```

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

#### 4. Scrcpy连接失败
- **Scrcpy未安装**：下载并安装Scrcpy
- **ADB未授权**：在电视上确认ADB授权
- **无线调试未开启**：在电视开发者选项中开启无线调试
- **IP地址错误**：确认电视IP地址正确
- **防火墙阻止**：检查防火墙是否阻止ADB连接（端口5555）

#### 5. Scrcpy画面卡顿
- **降低分辨率**：使用 `--max-size 800` 参数
- **降低帧率**：使用 `--max-fps 15` 参数
- **降低码率**：使用 `--bit-rate 1M` 参数
- **检查网络**：确保电视和电脑网络稳定
- **使用USB连接**：USB连接比无线更稳定

#### 6. Scrcpy无法控制
- **检查ADB连接**：使用 `adb devices` 确认连接
- **重新配对**：删除旧的ADB密钥重新配对
- **重启电视**：重启电视后重试
- **检查权限**：确保Scrcpy有足够权限

#### 7. 实时屏幕流卡顿（传统方式）
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
4. **集成Scrcpy功能**: 使用现有的Scrcpy API端点

### Scrcpy API参考
后端提供了完整的Scrcpy集成API：

#### 检查Scrcpy安装
```http
GET /api/v1/scrcpy/check
```
返回Scrcpy安装状态和路径。

#### 启动Scrcpy会话
```http
POST /api/v1/devices/{device_id}/scrcpy/start
```
启动Scrcpy远程控制会话。

#### 停止Scrcpy会话
```http
POST /api/v1/devices/{device_id}/scrcpy/stop
```
停止Scrcpy远程控制会话。

#### 获取Scrcpy状态
```http
GET /api/v1/devices/{device_id}/scrcpy/status
```
获取Scrcpy会话运行状态。

#### 获取Scrcpy命令
```http
GET /api/v1/devices/{device_id}/scrcpy/command
```
获取手动执行的Scrcpy命令。

#### ADB连接管理
```http
POST /api/v1/devices/{device_id}/adb/connect
POST /api/v1/devices/{device_id}/adb/disconnect
```
管理ADB无线调试连接。

### 测试
运行综合测试：
```bash
cd backend_server
source venv/bin/activate  # Windows: venv\Scripts\activate
python -c "from app.main import app; print('Backend OK')"
```

## 许可证

本项目采用MIT许可证。详见LICENSE文件。

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

如有问题或建议，请通过GitHub Issues提交。

---

**注意**: 本项目专为企业会议室环境设计，请确保遵守相关法律法规和公司政策使用。