import secrets
import os
import subprocess
import time
import asyncio
import base64
import json
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload

from .db import Base, engine, get_db
from .models import Device, DeviceHeartbeat, Policy, OperationLog
from .schemas import DeviceHeartbeatIn, DeviceOut, DeviceRegister, PolicyCreate, PolicyOut, OperationLogOut

Base.metadata.create_all(bind=engine)

def log_operation(db: Session, action: str, detail: str = None, device_id: int = None, device_name: str = None, operator: str = "admin"):
    log = OperationLog(action=action, detail=detail, device_id=device_id, device_name=device_name, operator=operator)
    db.add(log)
    db.commit()

def resolve_adb_path() -> str:
    env = os.environ.get("ADB_PATH")
    if env and os.path.exists(env):
        return env

    exe = "adb.exe" if os.name == "nt" else "adb"
    candidates: list[str] = []
    for var in ["ANDROID_HOME", "ANDROID_SDK_ROOT"]:
        root = os.environ.get(var)
        if root:
            candidates.append(os.path.join(root, "platform-tools", exe))

    if os.name == "nt":
        candidates.append(os.path.join(os.path.expanduser("~"), "AppData", "Local", "Android", "Sdk", "platform-tools", exe))

    for c in candidates:
        if os.path.exists(c):
            return c
    return "adb"

app = FastAPI(title="Mi TV Launcher Backend", version="0.1.0")

@app.on_event("startup")
def list_routes():
    for route in app.routes:
        methods = getattr(route, "methods", ["MOUNT"])
        print(f"Route: {route.path} [ {','.join(methods)} ]")

# Ensure directories exist
for path in ["static/ota", "static/screenshots", "static/uploads", "app/templates"]:
    if not os.path.exists(path):
        os.makedirs(path)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/v1/policies", response_model=PolicyOut)
def create_policy(payload: PolicyCreate, db: Session = Depends(get_db)):
    policy = Policy(**payload.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy

@app.get("/api/v1/policies", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_db)):
    return db.query(Policy).order_by(Policy.id.desc()).all()

@app.post("/api/v1/devices/register")
def register_device(payload: DeviceRegister, db: Session = Depends(get_db)):
    existing = db.query(Device).filter(Device.device_sn == payload.device_sn).first()
    if existing:
        for key, value in payload.model_dump().items():
            setattr(existing, key, value)
        db.commit()
        return {"token": existing.token, "device_id": existing.id}
    token = secrets.token_hex(24)
    device = Device(token=token, **payload.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"token": device.token, "device_id": device.id}

def auth_device(token: str, db: Session) -> Device:
    device = db.query(Device).options(joinedload(Device.policy)).filter(Device.token == token).first()
    if not device:
        raise HTTPException(status_code=401, detail="Invalid device token")
    return device

@app.post("/api/v1/devices/heartbeat")
def device_heartbeat(
    payload: DeviceHeartbeatIn,
    x_device_token: str = Header(default=""),
    db: Session = Depends(get_db),
):
    device = auth_device(x_device_token, db)
    update_data = payload.model_dump(exclude={"status", "message"}, exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(device, key, value)
    
    device.online = True
    db.add(DeviceHeartbeat(device_id=device.id, status=payload.status, message=payload.message))
    db.commit()
    db.refresh(device)
    policy = device.policy
    return {
        "policy": {
            "mode": policy.mode if policy else None,
            "target_app_package": policy.target_app_package if policy else None,
            "target_hdmi_port": policy.target_hdmi_port if policy else None,
            "fallback_mode": policy.fallback_mode if policy else None,
            "fallback_value": policy.fallback_value if policy else None,
        }
    }

@app.get("/api/v1/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.query(Device).order_by(Device.id.desc()).all()

@app.get("/api/device/status")
def device_status(ip: str, db: Session = Depends(get_db)):
    device = (
        db.query(Device)
        .filter((Device.eth_ip == ip) | (Device.wifi_ip == ip))
        .order_by(Device.id.desc())
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return {
        "ip": ip,
        "device_type": "电视机",
        "status": "已连接" if device.online else "未连接",
        "online": device.online,
        "device_id": device.id,
        "device_name": device.device_name,
        "model_name": device.model_name,
        "wifi_ip": device.wifi_ip,
        "eth_ip": device.eth_ip,
        "wifi_mac": device.wifi_mac,
        "eth_mac": device.eth_mac,
        "network_ssid": device.network_ssid,
        "policy_id": device.policy_id,
        "updated_at": device.updated_at.isoformat() if getattr(device, "updated_at", None) else None,
    }

@app.post("/api/v1/deploy-tv")
def remote_deploy(ip: str, db: Session = Depends(get_db)):
    """
    Connect to a remote TV via IP, install the launcher APK, and set the server URL.
    """
    adb_path = resolve_adb_path()
    
    # Try multiple possible APK locations
    possible_apk_paths = [
        "../android_app/app/build/outputs/apk/debug/app-debug.apk",
        "../../android_app/app/build/outputs/apk/debug/app-debug.apk",
        "../../backend/static/ota/app-debug.apk",
        "static/ota/app-debug.apk"
    ]
    
    apk_path = None
    for p in possible_apk_paths:
        if os.path.exists(p):
            apk_path = p
            break
    
    if not apk_path:
        return {"ok": False, "detail": "未找到安装包 (app-debug.apk)，请确保项目已编译。"}

    try:
        log_operation(db, "deploy_start", f"开始向 {ip} 部署应用")
        
        # 1. Connect via ADB
        # Force disconnect first to clean up any stale connections
        subprocess.run([adb_path, "disconnect", ip], timeout=5)
        conn_res = subprocess.run([adb_path, "connect", ip], capture_output=True, text=True, timeout=15)
        
        if "connected to" not in conn_res.stdout:
            return {"ok": False, "detail": f"ADB 连接失败: {conn_res.stdout.strip()}"}

        # Check for authentication failure
        auth_check = subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "echo", "ping"], capture_output=True, text=True, timeout=10)
        if "unauthorized" in auth_check.stderr or "unauthorized" in auth_check.stdout:
            return {"ok": False, "detail": "连接成功但未授权。请在电视屏幕上点击'始终允许'并确认授权。"}

        # 2. Install APK
        install_res = subprocess.run([adb_path, "-s", f"{ip}:5555", "install", "-r", apk_path], capture_output=True, text=True, timeout=120)
        if install_res.returncode != 0:
            return {"ok": False, "detail": f"安装失败: {install_res.stderr or install_res.stdout}"}

        # 3. Start the app
        subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "am", "start", "-n", "com.company.tvlauncher/.MainActivity"], timeout=15)
        
        # 4. Create default policy if none exists
        existing_policy = db.query(Policy).first()
        if not existing_policy:
            default_policy = Policy(
                name="默认策略",
                mode="app",
                target_app_package="com.android.settings",  # Default to Settings app
                target_hdmi_port=1,
                fallback_mode="app",
                fallback_value="com.android.settings",
                is_active=True
            )
            db.add(default_policy)
            db.commit()
            log_operation(db, "create_default_policy", "创建了默认策略")
        
        # 5. Get device info and register it
        try:
            # Get device serial number
            serial_res = subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "getprop", "ro.serialno"], 
                                       capture_output=True, text=True, timeout=10)
            device_sn = serial_res.stdout.strip() if serial_res.returncode == 0 else f"unknown_{ip}"
            
            # Get model name
            model_res = subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "getprop", "ro.product.model"], 
                                      capture_output=True, text=True, timeout=10)
            model_name = model_res.stdout.strip() if model_res.returncode == 0 else "Unknown"
            
            # Get MAC addresses
            wifi_mac_res = subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "cat", "/sys/class/net/wlan0/address"], 
                                         capture_output=True, text=True, timeout=10)
            wifi_mac = wifi_mac_res.stdout.strip() if wifi_mac_res.returncode == 0 else "00:00:00:00:00:00"
            
            eth_mac_res = subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "cat", "/sys/class/net/eth0/address"], 
                                        capture_output=True, text=True, timeout=10)
            eth_mac = eth_mac_res.stdout.strip() if eth_mac_res.returncode == 0 else "00:00:00:00:00:00"
            
            # Register device
            device_name = f"TV-{eth_mac[-6:].replace(':', '')}" if eth_mac != "00:00:00:00:00:00" else f"TV-{ip.replace('.', '')}"
            
            # Check if device already exists
            existing_device = db.query(Device).filter(Device.device_sn == device_sn).first()
            if existing_device:
                # Update existing device
                existing_device.device_name = device_name
                existing_device.model_name = model_name
                existing_device.eth_ip = ip
                existing_device.wifi_mac = wifi_mac
                existing_device.eth_mac = eth_mac
                existing_device.online = True
                db.commit()
                device_id = existing_device.id
                log_operation(db, "update_device", f"更新设备信息: {device_name}", device_id, device_name)
            else:
                # Create new device
                token = secrets.token_hex(24)
                device = Device(
                    device_sn=device_sn,
                    device_name=device_name,
                    model_name=model_name,
                    eth_ip=ip,
                    wifi_mac=wifi_mac,
                    eth_mac=eth_mac,
                    online=True,
                    token=token
                )
                db.add(device)
                db.commit()
                db.refresh(device)
                device_id = device.id
                log_operation(db, "register_device", f"注册新设备: {device_name}", device_id, device_name)
            
            # 6. Bind default policy to device
            default_policy = db.query(Policy).filter(Policy.name == "默认策略").first()
            if default_policy:
                device = db.query(Device).filter(Device.id == device_id).first()
                if device:
                    device.policy_id = default_policy.id
                    db.commit()
                    log_operation(db, "bind_default_policy", f"设备 {device_name} 绑定了默认策略", device_id, device_name)
        
        except Exception as device_err:
            # Continue even if device registration fails
            log_operation(db, "device_info_error", f"获取设备信息时出错: {str(device_err)}")
        
        log_operation(db, "deploy_success", f"已成功向 {ip} 远程部署 Launcher", None, ip)
        return {"ok": True, "message": f"部署成功，电视应已自动上线并绑定了默认策略"}
    except Exception as e:
        log_operation(db, "deploy_error", f"向 {ip} 部署时出错: {str(e)}")
        return {"ok": False, "detail": str(e)}

@app.post("/api/v1/devices/{device_id}/bind-policy/{policy_id}")
def bind_policy(device_id: int, policy_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not device or not policy:
        raise HTTPException(status_code=404, detail="Device or policy not found")
    device.policy_id = policy.id
    db.commit()
    log_operation(db, "bind_policy", f"设备 {device.device_name} 绑定了策略 {policy.name}", device_id, device.device_name)
    return {"ok": True}

@app.post("/api/v1/devices/{device_id}/room")
def update_room(device_id: int, room_name: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    old_room = device.room_name
    device.room_name = room_name
    db.commit()
    log_operation(db, "update_room", f"设备 {device.device_name} 的会议室从 {old_room} 改为 {room_name}", device_id, device.device_name)
    return {"ok": True}

@app.get("/api/v1/devices/{device_id}/screenshot")
def get_screenshot(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")

    adb_path = resolve_adb_path()
    local_path = f"static/screenshots/device_{device_id}.png"
    
    try:
        subprocess.run([adb_path, "connect", ip], timeout=5)
        subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "screencap", "-p", "/sdcard/screen.png"], check=True, timeout=10)
        subprocess.run([adb_path, "-s", f"{ip}:5555", "pull", "/sdcard/screen.png", local_path], check=True, timeout=15)
        log_operation(db, "screenshot", f"截取设备 {device.device_name} 画面", device_id, device.device_name)
        return {"ok": True, "url": f"/static/screenshots/device_{device_id}.png?t={int(time.time())}"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

# ==================== Scrcpy-like 远程控制功能 ====================

def check_scrcpy_available():
    """检查Scrcpy是否可用"""
    try:
        # 尝试运行scrcpy --version
        result = subprocess.run(["scrcpy", "--version"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except Exception:
        return False

def get_scrcpy_path():
    """获取Scrcpy可执行文件路径，如果未安装则尝试自动安装"""
    import sys
    import subprocess
    
    # 首先检查是否在PATH中
    if check_scrcpy_available():
        return "scrcpy"
    
    # 检查项目目录中的scrcpy
    project_scrcpy_paths = [
        os.path.join(os.path.dirname(__file__), "..", "scrcpy", "scrcpy.exe"),  # Windows
        os.path.join(os.path.dirname(__file__), "..", "scrcpy", "scrcpy"),      # Linux/macOS
    ]
    
    for path in project_scrcpy_paths:
        if os.path.exists(path):
            return path
    
    # 如果未找到，尝试自动安装
    print("Scrcpy未找到，尝试自动安装...")
    install_script = os.path.join(os.path.dirname(__file__), "..", "install_scrcpy.py")
    
    if os.path.exists(install_script):
        try:
            # 运行安装脚本
            result = subprocess.run(
                [sys.executable, install_script],
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                print("Scrcpy自动安装成功")
                # 安装后再次检查
                for path in project_scrcpy_paths:
                    if os.path.exists(path):
                        return path
            else:
                print(f"Scrcpy自动安装失败: {result.stderr}")
        except Exception as e:
            print(f"运行安装脚本时出错: {e}")
    
    # 检查常见系统安装位置
    system_paths = [
        "C:\\Program Files\\scrcpy\\scrcpy.exe",
        "C:\\scrcpy\\scrcpy.exe",
        os.path.join(os.path.expanduser("~"), "scrcpy", "scrcpy.exe"),
    ]
    
    for path in system_paths:
        if os.path.exists(path):
            return path
    
    return None

# Scrcpy连接管理器
class ScrcpyManager:
    def __init__(self):
        self.active_sessions = {}  # device_id -> process
    
    def start_scrcpy(self, device_id: int, ip: str, port: int = 5555):
        """启动Scrcpy会话"""
        try:
            scrcpy_path = get_scrcpy_path()
            if not scrcpy_path:
                return {"ok": False, "detail": "Scrcpy未安装，请先安装Scrcpy"}
            
            # 首先确保ADB连接
            adb_path = resolve_adb_path()
            subprocess.run([adb_path, "connect", f"{ip}:{port}"], timeout=10)
            
            # 启动Scrcpy
            # 使用简化的参数确保稳定启动
            cmd = [
                scrcpy_path,
                "--serial", f"{ip}:{port}",
                "--no-audio",
                "--max-fps", "30",
                "--max-size", "1024",
                "--always-on-top",
                "--window-title", f"小米电视远程控制 - {ip}"
            ]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.active_sessions[device_id] = process
            
            return {"ok": True, "message": f"Scrcpy会话已启动，PID: {process.pid}"}
        
        except Exception as e:
            return {"ok": False, "detail": f"启动Scrcpy失败: {str(e)}"}
    
    def stop_scrcpy(self, device_id: int):
        """停止Scrcpy会话"""
        if device_id in self.active_sessions:
            process = self.active_sessions[device_id]
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            del self.active_sessions[device_id]
            return {"ok": True, "message": "Scrcpy会话已停止"}
        return {"ok": False, "detail": "未找到活动的Scrcpy会话"}
    
    def get_session_status(self, device_id: int):
        """获取Scrcpy会话状态"""
        if device_id in self.active_sessions:
            process = self.active_sessions[device_id]
            if process.poll() is None:
                return {"ok": True, "status": "running", "pid": process.pid}
            else:
                return {"ok": True, "status": "stopped", "exit_code": process.returncode}
        return {"ok": False, "status": "not_running"}

scrcpy_manager = ScrcpyManager()

# Scrcpy相关API端点
@app.get("/api/v1/scrcpy/check")
async def check_scrcpy_installation():
    """检查Scrcpy安装状态"""
    scrcpy_path = get_scrcpy_path()
    if scrcpy_path:
        return {
            "ok": True, 
            "installed": True,
            "path": scrcpy_path,
            "message": "Scrcpy已安装"
        }
    else:
        return {
            "ok": False,
            "installed": False,
            "message": "Scrcpy未安装，请先安装Scrcpy"
        }

@app.post("/api/v1/devices/{device_id}/scrcpy/start")
async def start_scrcpy_session(device_id: int, db: Session = Depends(get_db)):
    """启动Scrcpy远程控制会话"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")
    
    result = scrcpy_manager.start_scrcpy(device_id, ip)
    
    if result["ok"]:
        log_operation(db, "start_scrcpy", f"启动Scrcpy远程控制会话", device_id, device.device_name)
    
    return result

@app.post("/api/v1/devices/{device_id}/scrcpy/stop")
async def stop_scrcpy_session(device_id: int, db: Session = Depends(get_db)):
    """停止Scrcpy远程控制会话"""
    result = scrcpy_manager.stop_scrcpy(device_id)
    
    if result["ok"]:
        device = db.query(Device).filter(Device.id == device_id).first()
        if device:
            log_operation(db, "stop_scrcpy", f"停止Scrcpy远程控制会话", device_id, device.device_name)
    
    return result

@app.get("/api/v1/devices/{device_id}/scrcpy/status")
async def get_scrcpy_status(device_id: int):
    """获取Scrcpy会话状态"""
    return scrcpy_manager.get_session_status(device_id)

# 简化的ADB无线调试API（用于前端直接控制）
@app.post("/api/v1/devices/{device_id}/adb/connect")
async def adb_connect_device(device_id: int, db: Session = Depends(get_db)):
    """通过ADB连接到设备"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")
    
    adb_path = resolve_adb_path()
    
    try:
        # 尝试连接
        result = subprocess.run([adb_path, "connect", f"{ip}:5555"], capture_output=True, text=True, timeout=15)
        
        if "connected to" in result.stdout or "already connected" in result.stdout:
            log_operation(db, "adb_connect", f"ADB连接成功: {ip}", device_id, device.device_name)
            return {"ok": True, "message": f"已连接到 {ip}:5555"}
        else:
            log_operation(db, "adb_connect_failed", f"ADB连接失败: {result.stdout}", device_id, device.device_name)
            return {"ok": False, "detail": f"连接失败: {result.stdout}"}
    
    except Exception as e:
        log_operation(db, "adb_connect_error", f"ADB连接异常: {str(e)}", device_id, device.device_name)
        return {"ok": False, "detail": str(e)}

@app.post("/api/v1/devices/{device_id}/adb/disconnect")
async def adb_disconnect_device(device_id: int, db: Session = Depends(get_db)):
    """断开ADB连接"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")
    
    adb_path = resolve_adb_path()
    
    try:
        result = subprocess.run([adb_path, "disconnect", f"{ip}:5555"], capture_output=True, text=True, timeout=10)
        
        log_operation(db, "adb_disconnect", f"ADB断开连接: {ip}", device_id, device.device_name)
        return {"ok": True, "message": f"已断开与 {ip}:5555 的连接"}
    
    except Exception as e:
        log_operation(db, "adb_disconnect_error", f"ADB断开连接异常: {str(e)}", device_id, device.device_name)
        return {"ok": False, "detail": str(e)}

# 生成Scrcpy启动命令（供用户手动执行）
@app.get("/api/v1/devices/{device_id}/scrcpy/command")
async def get_scrcpy_command(device_id: int, db: Session = Depends(get_db)):
    """获取Scrcpy启动命令（供用户手动执行）"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")
    
    scrcpy_path = get_scrcpy_path()
    if not scrcpy_path:
        return {"ok": False, "detail": "Scrcpy未安装"}
    
    # 生成命令
    command = f'"{scrcpy_path}" --serial {ip}:5555 --no-audio --max-fps 30 --bit-rate 2M --max-size 1024'
    
    return {
        "ok": True,
        "command": command,
        "description": "在命令行中执行此命令启动Scrcpy",
        "steps": [
            "1. 确保已安装Scrcpy",
            "2. 确保电视已开启ADB调试",
            "3. 复制上面的命令到命令行执行",
            "4. 等待Scrcpy窗口出现"
        ]
    }

@app.post("/api/v1/devices/{device_id}/input")
def device_input(device_id: int, action: str, key: str = None, x: int = None, y: int = None, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")

    adb_path = resolve_adb_path()
    
    try:
        subprocess.run([adb_path, "connect", ip], timeout=5)
        if action == "key":
            key_map = {
                "UP": "19", "DOWN": "20", "LEFT": "21", "RIGHT": "22", "OK": "66", 
                "BACK": "4", "HOME": "3", "MENU": "82", "VOLUP": "24", "VOLDOWN": "25"
            }
            code = key_map.get(key.upper(), key)
            subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "input", "keyevent", code], check=True)
        elif action == "tap":
            subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "input", "tap", str(x), str(y)], check=True)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

@app.post("/api/v1/devices/{device_id}/adb-install")
def adb_install(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")
    
    adb_path = resolve_adb_path()
    # Search for APK in android_app folder
    apk_path = "../android_app/app/build/outputs/apk/debug/app-debug.apk"
    
    if not os.path.exists(apk_path):
        return {"ok": False, "detail": f"APK not found at {apk_path}"}

    try:
        subprocess.run([adb_path, "connect", ip], timeout=10)
        result = subprocess.run([adb_path, "-s", f"{ip}:5555", "install", "-r", apk_path], capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
             return {"ok": False, "detail": result.stderr or result.stdout}
        subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "am", "start", "-n", "com.company.tvlauncher/.MainActivity"], timeout=10)
        log_operation(db, "adb_install", f"为设备 {device.device_name} 安装最新APK", device_id, device.device_name)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

@app.post("/api/v1/devices/{device_id}/uninstall")
def uninstall_app(device_id: int, package_name: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")

    adb_path = resolve_adb_path()
    
    try:
        subprocess.run([adb_path, "connect", ip], timeout=5)
        result = subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "pm", "uninstall", package_name], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"ok": False, "detail": result.stderr or result.stdout}
        log_operation(db, "uninstall", f"从设备 {device.device_name} 卸载应用 {package_name}", device_id, device.device_name)
        return {"ok": True, "message": "卸载成功"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

@app.post("/api/v1/devices/{device_id}/install-uploaded")
def install_uploaded(device_id: int, filename: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")

    adb_path = resolve_adb_path()
    apk_path = f"static/uploads/{filename}"
    
    if not os.path.exists(apk_path):
        return {"ok": False, "detail": f"APK 文件不存在: {filename}"}

    try:
        subprocess.run([adb_path, "connect", ip], timeout=5)
        result = subprocess.run([adb_path, "-s", f"{ip}:5555", "install", "-r", apk_path], capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return {"ok": False, "detail": result.stderr or result.stdout}
        log_operation(db, "install_uploaded", f"为设备 {device.device_name} 安装上传的APK: {filename}", device_id, device.device_name)
        return {"ok": True, "message": "安装成功"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

@app.post("/api/v1/upload-apk")
async def upload_apk(file: UploadFile = File(...)):
    if not file.filename.endswith('.apk'):
        raise HTTPException(status_code=400, detail="只支持 APK 文件")
    
    upload_dir = "static/uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return {"ok": True, "filename": file.filename, "url": f"/static/uploads/{file.filename}"}

@app.get("/", response_class=HTMLResponse)
def index():
    try:
        with open("app/templates/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "<h1>Dashboard Template Missing</h1>"

@app.delete("/api/v1/policies/{policy_id}")
def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    policy_name = policy.name
    db.delete(policy)
    db.commit()
    log_operation(db, "delete_policy", f"删除了策略: {policy_name}")
    return {"ok": True}

@app.delete("/api/v1/devices/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device_name = device.device_name
    db.delete(device)
    db.commit()
    log_operation(db, "delete_device", f"移除了设备: {device_name}", device_id, device_name)
    return {"ok": True}

@app.get("/api/v1/logs", response_model=list[OperationLogOut])
def list_logs(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(OperationLog).order_by(OperationLog.id.desc()).limit(limit).all()

@app.delete("/api/v1/logs")
def clear_logs(db: Session = Depends(get_db)):
    db.query(OperationLog).delete()
    db.commit()
    return {"ok": True}

@app.get("/api/v1/ota/check")
def ota_check(version: str = "0.0.0"):
    latest_version = "0.1.5"
    if version < latest_version:
        return {
            "update_available": True,
            "latest_version": latest_version,
            "url": "http://localhost:8000/static/ota/app-debug.apk",
            "silent": True
        }
    return {"update_available": False}

# WebSocket连接管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}
    
    async def connect(self, device_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[device_id] = websocket
    
    def disconnect(self, device_id: int):
        if device_id in self.active_connections:
            del self.active_connections[device_id]
    
    async def send_screenshot(self, device_id: int, image_data: str):
        if device_id in self.active_connections:
            try:
                await self.active_connections[device_id].send_json({
                    "type": "screenshot",
                    "data": image_data
                })
            except:
                self.disconnect(device_id)

manager = ConnectionManager()

# 实时屏幕流WebSocket端点
@app.websocket("/ws/devices/{device_id}/screen")
async def websocket_screen_stream(websocket: WebSocket, device_id: int):
    await manager.connect(device_id, websocket)
    try:
        while True:
            # 等待客户端消息（控制指令）
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "control":
                    # 处理控制指令
                    action = message.get("action")
                    if action == "tap":
                        x = message.get("x")
                        y = message.get("y")
                        if x is not None and y is not None:
                            # 执行点击操作
                            db = next(get_db())
                            device = db.query(Device).filter(Device.id == device_id).first()
                            if device:
                                ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
                                if ip and ip != "0.0.0.0":
                                    adb_path = resolve_adb_path()
                                    subprocess.run([adb_path, "connect", ip], timeout=5)
                                    subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "input", "tap", str(x), str(y)], timeout=5)
                                    log_operation(db, "websocket_tap", f"通过WebSocket点击位置 ({x}, {y})", device_id, device.device_name)
                    elif action == "key":
                        key = message.get("key")
                        if key:
                            db = next(get_db())
                            device = db.query(Device).filter(Device.id == device_id).first()
                            if device:
                                ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
                                if ip and ip != "0.0.0.0":
                                    adb_path = resolve_adb_path()
                                    subprocess.run([adb_path, "connect", ip], timeout=5)
                                    subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "input", "keyevent", key], timeout=5)
                                    log_operation(db, "websocket_key", f"通过WebSocket发送按键: {key}", device_id, device.device_name)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(device_id)

# 屏幕截图流端点（供前端轮询）
@app.get("/api/v1/devices/{device_id}/screen-stream")
async def screen_stream(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")
    
    adb_path = resolve_adb_path()
    local_path = f"static/screenshots/device_{device_id}_stream.png"
    
    try:
        # 连接设备
        subprocess.run([adb_path, "connect", ip], timeout=5)
        
        # 截取屏幕
        subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "screencap", "-p", "/sdcard/screen_stream.png"], check=True, timeout=10)
        
        # 拉取截图
        subprocess.run([adb_path, "-s", f"{ip}:5555", "pull", "/sdcard/screen_stream.png", local_path], check=True, timeout=15)
        
        # 读取图片并转换为base64
        with open(local_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # 发送给WebSocket客户端
        await manager.send_screenshot(device_id, image_data)
        
        return {"ok": True, "message": "Screenshot captured and sent"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

# 鼠标控制端点
@app.post("/api/v1/devices/{device_id}/mouse")
async def mouse_control(device_id: int, action: str, x: int = None, y: int = None, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")
    
    adb_path = resolve_adb_path()
    
    try:
        subprocess.run([adb_path, "connect", ip], timeout=5)
        
        if action == "tap":
            if x is not None and y is not None:
                subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "input", "tap", str(x), str(y)], check=True, timeout=5)
                log_operation(db, "mouse_tap", f"点击位置 ({x}, {y})", device_id, device.device_name)
                return {"ok": True, "message": f"Tap at ({x}, {y})"}
            else:
                return {"ok": False, "detail": "Missing x or y coordinates"}
        
        elif action == "swipe":
            # 需要起始点和结束点
            return {"ok": False, "detail": "Swipe action requires start and end coordinates"}
        
        elif action == "drag":
            # 拖拽操作
            return {"ok": False, "detail": "Drag action requires start and end coordinates"}
        
        else:
            return {"ok": False, "detail": f"Unknown action: {action}"}
    
    except Exception as e:
        return {"ok": False, "detail": str(e)}
