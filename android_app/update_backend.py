import os
import secrets
import subprocess

# Define base directory relative to this script
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.join(base_dir, "backend_server")

backend_main_path = os.path.join(backend_dir, "app", "main.py")
backend_models_path = os.path.join(backend_dir, "app", "models.py")
backend_schemas_path = os.path.join(backend_dir, "app", "schemas.py")
backend_templates_dir = os.path.join(backend_dir, "app", "templates")
backend_db_path = os.path.join(backend_dir, "app", "db.py")

# 0. Update db.py to use SQLite
db_content = """import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./tv_launcher.db",
)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
"""
with open(backend_db_path, 'w', encoding='utf-8') as f:
    f.write(db_content)

# 1. Update models.py
models_content = """from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    target_app_package: Mapped[str | None] = mapped_column(String(256), nullable=True)
    target_hdmi_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fallback_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    fallback_value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_sn: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    device_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True) # Legacy field
    wifi_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    eth_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wifi_mac: Mapped[str | None] = mapped_column(String(32), nullable=True)
    eth_mac: Mapped[str | None] = mapped_column(String(32), nullable=True)
    network_ssid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    installed_apps: Mapped[str | None] = mapped_column(Text, nullable=True)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    policy_id: Mapped[int | None] = mapped_column(ForeignKey("policies.id"), nullable=True)
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    policy = relationship("Policy")

class DeviceHeartbeat(Base):
    __tablename__ = "device_heartbeats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ok")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

class OperationLog(Base):
    __tablename__ = "operation_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator: Mapped[str] = mapped_column(String(128), default="admin")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
"""
with open(backend_models_path, 'w', encoding='utf-8') as f:
    f.write(models_content)

# 2. Update schemas.py
schemas_content = """from pydantic import BaseModel
from typing import Optional

class PolicyBase(BaseModel):
    name: str
    mode: str
    target_app_package: Optional[str] = None
    target_hdmi_port: Optional[int] = None
    fallback_mode: Optional[str] = None
    fallback_value: Optional[str] = None
    is_active: bool = True

class PolicyCreate(PolicyBase):
    pass

class PolicyOut(PolicyBase):
    id: int
    class Config:
        from_attributes = True

class DeviceRegister(BaseModel):
    device_sn: str
    device_name: str
    model_name: Optional[str] = None
    wifi_mac: Optional[str] = None
    eth_mac: Optional[str] = None

class DeviceHeartbeatIn(BaseModel):
    wifi_ip: Optional[str] = None
    eth_ip: Optional[str] = None
    wifi_mac: Optional[str] = None
    eth_mac: Optional[str] = None
    network_ssid: Optional[str] = None
    installed_apps: Optional[str] = None
    status: str = "ok"
    message: Optional[str] = None

class DeviceOut(BaseModel):
    id: int
    device_sn: str
    device_name: str
    model_name: Optional[str]
    wifi_ip: Optional[str]
    eth_ip: Optional[str]
    wifi_mac: Optional[str]
    eth_mac: Optional[str]
    network_ssid: Optional[str]
    installed_apps: Optional[str]
    online: bool
    policy_id: Optional[int]
    class Config:
        from_attributes = True

class OperationLogOut(BaseModel):
    id: int
    device_id: Optional[int]
    device_name: Optional[str]
    action: str
    detail: Optional[str]
    operator: str
    created_at: str
    class Config:
        from_attributes = True
"""
with open(backend_schemas_path, 'w', encoding='utf-8') as f:
    f.write(schemas_content)

# 3. Update main.py
full_main_content = """import secrets
import os
import subprocess
import time
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File
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

app = FastAPI(title="Mi TV Launcher Backend", version="0.1.0")

if not os.path.exists("static/ota"):
    os.makedirs("static/ota")
if not os.path.exists("static/screenshots"):
    os.makedirs("static/screenshots")
if not os.path.exists("static/uploads"):
    os.makedirs("static/uploads")
if not os.path.exists("app/templates"):
    os.makedirs("app/templates")

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
    # Only update fields that are not None
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

@app.get("/api/v1/devices/{device_id}/screenshot")
def get_screenshot(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")

    adb_path = "D:/MyConfiguration/admin/AppData/Local/Android/Sdk/platform-tools/adb.exe"
    local_path = f"static/screenshots/device_{device_id}.png"
    
    try:
        subprocess.run([adb_path, "connect", ip], timeout=5)
        # Take screenshot on device
        subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "screencap", "-p", "/sdcard/screen.png"], check=True, timeout=10)
        # Pull to server
        subprocess.run([adb_path, "-s", f"{ip}:5555", "pull", "/sdcard/screen.png", local_path], check=True, timeout=15)
        log_operation(db, "screenshot", f"截取设备 {device.device_name} 画面", device_id, device.device_name)
        return {"ok": True, "url": f"/static/screenshots/device_{device_id}.png?t={int(time.time())}"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

@app.post("/api/v1/devices/{device_id}/input")
def device_input(device_id: int, action: str, key: str = None, x: int = None, y: int = None, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="Device has no valid IP for ADB")

    adb_path = "D:/MyConfiguration/admin/AppData/Local/Android/Sdk/platform-tools/adb.exe"
    
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
    
    adb_path = "D:/MyConfiguration/admin/AppData/Local/Android/Sdk/platform-tools/adb.exe"
    apk_path = "D:/MyConfiguration/admin/AndroidStudioProjects/mi-tv-launcher/tv-launcher-app/app/build/outputs/apk/debug/app-debug.apk"
    
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

    adb_path = "D:/MyConfiguration/admin/AppData/Local/Android/Sdk/platform-tools/adb.exe"
    
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

    adb_path = "D:/MyConfiguration/admin/AppData/Local/Android/Sdk/platform-tools/adb.exe"
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
"""
with open(backend_main_path, 'w', encoding='utf-8') as f:
    f.write(full_main_content)

# 4. Enhanced index.html
enhanced_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meeting TV Launcher 控制台</title>
    <style>
        body { font-family: -apple-system, sans-serif; padding: 20px; background: #f0f2f5; color: #333; }
        .container { max-width: 1400px; margin: 0 auto; }
        .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 24px; }
        h1 { color: #1a73e8; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #fafafa; }
        .online { color: #1e7e34; font-weight: bold; }
        .offline { color: #d93025; }
        .btn { padding: 6px 12px; background: #1a73e8; color: white; border: none; border-radius: 4px; cursor: pointer; margin-right: 5px; }
        .btn-danger { background: #d93025; }
        .btn-success { background: #1e7e34; }
        .btn-info { background: #17a2b8; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, select { padding: 8px; border: 1px solid #ddd; border-radius: 4px; width: 100%; box-sizing: border-box; }
        .modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); }
        .modal-content { background: white; margin: 5% auto; padding: 20px; border-radius: 8px; width: 450px; }
        .app-list-tag { display: inline-block; background: #e8f0fe; color: #1967d2; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; margin: 2px; }
        .net-info { font-size: 0.85rem; line-height: 1.4; }
        .net-label { color: #666; width: 50px; display: inline-block; }
        #screenshotImg { width: 100%; border-radius: 4px; border: 1px solid #ddd; }
        .app-item { display: flex; justify-content: space-between; align-items: center; padding: 8px; border-bottom: 1px solid #eee; }
        .app-item:last-child { border-bottom: none; }
        .app-name { font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Meeting TV Launcher 控制台 <button class="btn" style="background:#17a2b8; font-size:0.8rem" onclick="showLogs()">📋 操作日志</button></h1>
        
        <div class="card">
            <h2>设备管理</h2>
            <table id="deviceTable">
                <thead>
                    <tr>
                        <th>设备名称</th>
                        <th>SN / 型号</th>
                        <th>网络详情 (Wired / WiFi)</th>
                        <th>状态 / SSID</th>
                        <th>执行策略</th>
                        <th>高级操作</th>
                    </tr>
                </thead>
                <tbody id="deviceBody"></tbody>
            </table>
        </div>

        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h2>策略库</h2>
                <button class="btn" onclick="showAddPolicy()">+ 新增策略</button>
            </div>
            <table id="policyTable">
                <thead>
                    <tr>
                        <th>策略名称</th>
                        <th>模式</th>
                        <th>目标</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="policyBody"></tbody>
            </table>
        </div>
    </div>

    <!-- Add Policy Modal -->
    <div id="policyModal" class="modal">
        <div class="modal-content">
            <h3>新增策略</h3>
            <div class="form-group">
                <label>策略名称</label>
                <input type="text" id="pName" placeholder="如：投屏App启动">
            </div>
            <div class="form-group">
                <label>执行模式</label>
                <select id="pMode" onchange="toggleInputs()">
                    <option value="app">启动 APP</option>
                    <option value="hdmi">切换 HDMI</option>
                </select>
            </div>
            <div id="appInputGroup" class="form-group">
                <label>选择已安装的 APP (自动识别)</label>
                <select id="pAppSelect" onchange="syncAppInput()">
                    <option value="">-- 请选择或在下方手动输入 --</option>
                </select>
                <label style="margin-top:10px">手动输入包名</label>
                <input type="text" id="pPackage" placeholder="com.example.app">
            </div>
            <div id="hdmiInput" class="form-group" style="display:none">
                <label>HDMI 端口</label>
                <input type="number" id="pHdmi" value="1">
            </div>
            <div style="text-align: right; margin-top:20px;">
                <button class="btn" style="background:#888" onclick="closeModal()">取消</button>
                <button class="btn" onclick="savePolicy()">保存</button>
            </div>
        </div>
    </div>

    <!-- Screenshot & Remote Modal -->
    <div id="screenshotModal" class="modal">
        <div class="modal-content" style="width: 900px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 id="screenshotTitle" style="margin:0">远程控制</h3>
                <button class="btn btn-info" id="refreshScreenshotBtn">🔄 刷新画面</button>
            </div>
            
            <div style="display: flex; gap: 20px;">
                <!-- Left: Screen -->
                <div style="flex: 2; position: relative;">
                    <div id="screenshotLoading" style="text-align: center; padding: 100px; background: #eee; border-radius: 4px;">正在截取电视画面...</div>
                    <img id="screenshotImg" style="display:none; width: 100%; cursor: crosshair;" onclick="handleScreenClick(event)">
                </div>
                
                <!-- Right: Controls -->
                <div style="flex: 1; display: flex; flex-direction: column; gap: 10px;">
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; text-align: center;">
                        <div></div>
                        <button class="btn" onclick="sendKey('UP')">▲</button>
                        <div></div>
                        <button class="btn" onclick="sendKey('LEFT')">◀</button>
                        <button class="btn btn-success" onclick="sendKey('OK')">OK</button>
                        <button class="btn" onclick="sendKey('RIGHT')">▶</button>
                        <div></div>
                        <button class="btn" onclick="sendKey('DOWN')">▼</button>
                        <div></div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px;">
                        <button class="btn" style="background:#666" onclick="sendKey('BACK')">返回</button>
                        <button class="btn" style="background:#666" onclick="sendKey('HOME')">主页</button>
                        <button class="btn" style="background:#666" onclick="sendKey('MENU')">菜单</button>
                        <button class="btn" style="background:#666" onclick="sendKey('VOLUP')">音量+</button>
                        <button class="btn" style="background:#666" onclick="sendKey('VOLDOWN')">音量-</button>
                    </div>
                    
                    <div style="margin-top: 20px; font-size: 0.8rem; color: #666;">
                        提示：点击画面可模拟点击电视屏幕。
                    </div>
                </div>
            </div>

            <div style="text-align: right; margin-top:20px;">
                <button class="btn" onclick="closeScreenshotModal()">关闭远程</button>
            </div>
        </div>
    </div>

    <!-- App Management Modal -->
    <div id="appModal" class="modal">
        <div class="modal-content" style="width: 600px;">
            <h3 id="appModalTitle">应用管理</h3>
            <div id="appList" style="max-height: 300px; overflow-y: auto; border: 1px solid #eee; border-radius: 4px; margin: 10px 0;"></div>
            <div style="border-top: 1px solid #eee; padding-top: 15px;">
                <h4 style="margin: 0 0 10px 0;">上传安装第三方 APK</h4>
                <input type="file" id="apkFileInput" accept=".apk" style="margin-bottom: 10px;">
                <button class="btn btn-success" onclick="uploadApk()">上传并安装到本设备</button>
            </div>
            <div style="text-align: right; margin-top:20px;">
                <button class="btn" style="background:#888" onclick="closeAppModal()">关闭</button>
            </div>
        </div>
    </div>

    <!-- Operation Log Modal -->
    <div id="logModal" class="modal">
        <div class="modal-content" style="width: 800px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 style="margin:0">操作日志</h3>
                <div>
                    <button class="btn btn-danger" style="background:#d93025" onclick="clearLogs()">清空日志</button>
                    <button class="btn" style="background:#888" onclick="closeLogModal()">关闭</button>
                </div>
            </div>
            <div id="logList" style="max-height: 400px; overflow-y: auto; font-size: 0.85rem;"></div>
        </div>
    </div>

    <script>
        let allInstalledApps = new Set();
        let currentRemoteDeviceId = null;

        async function loadData() {
            const policies = await (await fetch('/api/v1/policies')).json();
            const devices = await (await fetch('/api/v1/devices')).json();

            allInstalledApps.clear();
            devices.forEach(d => {
                if (d.installed_apps) {
                    try {
                        const apps = JSON.parse(d.installed_apps);
                        apps.forEach(app => allInstalledApps.add(app));
                    } catch(e) {}
                }
            });

            const select = document.getElementById('pAppSelect');
            const currentVal = select.value;
            select.innerHTML = '<option value="">-- 请选择或在下方手动输入 --</option>';
            Array.from(allInstalledApps).sort().forEach(app => {
                const opt = document.createElement('option');
                opt.value = app;
                opt.textContent = app;
                select.appendChild(opt);
            });
            select.value = currentVal;

            document.getElementById('policyBody').innerHTML = policies.map(p => `
                <tr>
                    <td><strong>${p.name}</strong></td>
                    <td>${p.mode.toUpperCase()}</td>
                    <td>${p.mode === 'app' ? '<code>' + p.target_app_package + '</code>' : 'HDMI ' + p.target_hdmi_port}</td>
                    <td><button class="btn btn-danger" onclick="deletePolicy(${p.id})">删除</button></td>
                </tr>
            `).join('');

            document.getElementById('deviceBody').innerHTML = devices.map(d => {
                let appTags = '';
                if (d.installed_apps) {
                    try {
                        const apps = JSON.parse(d.installed_apps);
                        appTags = '<div style="margin-top:5px">' + apps.slice(0, 3).map(a => `<span class="app-list-tag">${a.split('.').pop()}</span>`).join('') + (apps.length > 3 ? '...' : '') + '</div>';
                    } catch(e) {}
                }
                
                return `
                <tr>
                    <td>${d.device_name}<br><small>${d.model_name || '-'}</small>${appTags}</td>
                    <td><code>${d.device_sn}</code></td>
                    <td class="net-info">
                        <div><span class="net-label">Wired:</span> ${d.eth_ip || '0.0.0.0'} / <small>${d.eth_mac || 'N/A'}</small></div>
                        <div><span class="net-label">WiFi:</span> ${d.wifi_ip || '0.0.0.0'} / <small>${d.wifi_mac || 'N/A'}</small></div>
                    </td>
                    <td>
                        <span class="${d.online ? 'online' : 'offline'}">${d.online ? '● 在线' : '○ 离线'}</span><br>
                        <small>${d.network_ssid || '未连接无线'}</small>
                    </td>
                    <td>
                        <select id="sel-${d.id}" style="width:150px">
                            <option value="">未分配</option>
                            ${policies.map(p => `<option value="${p.id}" ${d.policy_id === p.id ? 'selected' : ''}>${p.name}</option>`).join('')}
                        </select>
                        <button class="btn" onclick="bindPolicy(${d.id})">下发</button>
                    </td>
                    <td>
                        <button class="btn btn-info" onclick="takeScreenshot(${d.id}, '${d.device_name}')">📺 远程控制</button>
                        <button class="btn btn-success" onclick="confirmAdbInstall(${d.id}, '${d.device_name}')">安装 APK</button>
                        <button class="btn" style="background:#93259c" onclick="manageApps(${d.id}, '${d.device_name}')">📱 管理应用</button>
                        <button class="btn btn-danger" onclick="deleteDevice(${d.id})">移除</button>
                    </td>
                </tr>
            `}).join('');
        }

        function showAddPolicy() { document.getElementById('policyModal').style.display = 'block'; }
        function closeModal() { document.getElementById('policyModal').style.display = 'none'; }
        function closeScreenshotModal() { 
            document.getElementById('screenshotModal').style.display = 'none'; 
            currentRemoteDeviceId = null;
        }
        
        function toggleInputs() {
            const mode = document.getElementById('pMode').value;
            document.getElementById('appInputGroup').style.display = mode === 'app' ? 'block' : 'none';
            document.getElementById('hdmiInput').style.display = mode === 'hdmi' ? 'block' : 'none';
        }
        function syncAppInput() {
            const selected = document.getElementById('pAppSelect').value;
            if (selected) {
                document.getElementById('pPackage').value = selected;
            }
        }

        async function takeScreenshot(deviceId, deviceName) {
            currentRemoteDeviceId = deviceId;
            document.getElementById('screenshotModal').style.display = 'block';
            document.getElementById('screenshotTitle').innerText = `正在控制 "${deviceName}"`;
            document.getElementById('screenshotLoading').style.display = 'block';
            document.getElementById('screenshotImg').style.display = 'none';
            
            const refreshBtn = document.getElementById('refreshScreenshotBtn');
            refreshBtn.onclick = () => takeScreenshot(deviceId, deviceName);

            try {
                const resp = await fetch(`/api/v1/devices/${deviceId}/screenshot`);
                const result = await resp.json();
                if (result.ok) {
                    const img = document.getElementById('screenshotImg');
                    img.src = result.url;
                    img.style.display = 'block';
                    document.getElementById('screenshotLoading').style.display = 'none';
                } else {
                    alert('画面截取失败: ' + (result.detail || '未知错误'));
                }
            } catch (e) {
                alert('网络请求失败');
            }
        }

        async function sendKey(key) {
            if (!currentRemoteDeviceId) return;
            const resp = await fetch(`/api/v1/devices/${currentRemoteDeviceId}/input?action=key&key=${key}`, { method: 'POST' });
            const result = await resp.json();
            if (!result.ok) alert('操作失败: ' + (result.detail || '未知错误'));
            else {
                // Refresh screen after a short delay to see result
                setTimeout(() => {
                    const btn = document.getElementById('refreshScreenshotBtn');
                    if (btn) btn.click();
                }, 1000);
            }
        }

        async function handleScreenClick(event) {
            if (!currentRemoteDeviceId) return;
            const img = event.target;
            const rect = img.getBoundingClientRect();
            
            // Assume 1080p for now as most TVs are 1080p or scale to it via ADB
            // Better would be to get resolution from device, but let's assume 1920x1080
            const x = Math.round((event.clientX - rect.left) / rect.width * 1920);
            const y = Math.round((event.clientY - rect.top) / rect.height * 1080);
            
            const resp = await fetch(`/api/v1/devices/${currentRemoteDeviceId}/input?action=tap&x=${x}&y=${y}`, { method: 'POST' });
            const result = await resp.json();
            if (!result.ok) alert('点击失败: ' + (result.detail || '未知错误'));
            else {
                setTimeout(() => {
                    const btn = document.getElementById('refreshScreenshotBtn');
                    if (btn) btn.click();
                }, 1000);
            }
        }

        async function savePolicy() {
            const payload = {
                name: document.getElementById('pName').value,
                mode: document.getElementById('pMode').value,
                target_app_package: document.getElementById('pPackage').value,
                target_hdmi_port: parseInt(document.getElementById('pHdmi').value)
            };
            const resp = await fetch('/api/v1/policies', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (resp.ok) { closeModal(); loadData(); }
        }

        async function deletePolicy(id) {
            if (confirm('确定删除此策略？')) {
                await fetch(`/api/v1/policies/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        async function deleteDevice(id) {
            if (confirm('确定移除此设备？')) {
                await fetch(`/api/v1/devices/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        async function bindPolicy(deviceId) {
            const policyId = document.getElementById(`sel-${deviceId}`).value;
            await fetch(`/api/v1/devices/${deviceId}/bind-policy/${policyId}`, { method: 'POST' });
            alert('已下发策略');
            loadData();
        }

        async function confirmAdbInstall(deviceId, deviceName) {
            if (confirm(`确定要为设备 "${deviceName}" 安装最新版本的 APK 吗？这可能需要几十秒时间。`)) {
                const btn = event.target;
                const oldText = btn.innerText;
                btn.innerText = "正在安装...";
                btn.disabled = true;

                try {
                    const resp = await fetch(`/api/v1/devices/${deviceId}/adb-install`, { method: 'POST' });
                    const result = await resp.json();
                    if (result.ok) {
                        alert('安装成功！应用已自动启动。');
                    } else {
                        alert('安装失败: ' + (result.detail || '未知错误'));
                    }
                } catch (e) {
                    alert('网络请求失败');
                } finally {
                    btn.innerText = oldText;
                    btn.disabled = false;
                }
            }
        }

        let currentAppDeviceId = null;

        async function manageApps(deviceId, deviceName) {
            currentAppDeviceId = deviceId;
            document.getElementById('appModalTitle').innerText = `应用管理 - ${deviceName}`;
            document.getElementById('appModal').style.display = 'block';

            const devices = await (await fetch('/api/v1/devices')).json();
            const device = devices.find(d => d.id === deviceId);

            const appList = document.getElementById('appList');
            if (device && device.installed_apps) {
                try {
                    const apps = JSON.parse(device.installed_apps);
                    appList.innerHTML = apps.map(app => `
                        <div class="app-item">
                            <span class="app-name">${app}</span>
                            <button class="btn btn-danger" style="padding: 2px 8px; font-size: 0.75rem;" onclick="uninstallApp('${app}')">卸载</button>
                        </div>
                    `).join('');
                } catch(e) {
                    appList.innerHTML = '<div style="padding: 10px; color: #999;">无法解析应用列表</div>';
                }
            } else {
                appList.innerHTML = '<div style="padding: 10px; color: #999;">未获取到应用列表</div>';
            }
        }

        function closeAppModal() {
            document.getElementById('appModal').style.display = 'none';
            currentAppDeviceId = null;
        }

        async function uninstallApp(packageName) {
            if (!confirm(`确定要卸载应用 ${packageName} 吗？`)) return;

            try {
                const resp = await fetch(`/api/v1/devices/${currentAppDeviceId}/uninstall?package_name=${encodeURIComponent(packageName)}`, { method: 'POST' });
                const result = await resp.json();
                if (result.ok) {
                    alert('卸载成功');
                    loadData();
                    manageApps(currentAppDeviceId, '');
                } else {
                    alert('卸载失败: ' + (result.detail || result.message));
                }
            } catch(e) {
                alert('请求失败');
            }
        }

        async function uploadApk() {
            const fileInput = document.getElementById('apkFileInput');
            if (!fileInput.files || fileInput.files.length === 0) {
                alert('请选择 APK 文件');
                return;
            }

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);

            try {
                const resp = await fetch('/api/v1/upload-apk', { method: 'POST', body: formData });
                const result = await resp.json();
                if (result.ok) {
                    alert('上传成功，正在安装到设备...');
                    const installResp = await fetch(`/api/v1/devices/${currentAppDeviceId}/install-uploaded?filename=${encodeURIComponent(result.filename)}`, { method: 'POST' });
                    const installResult = await installResp.json();
                    if (installResult.ok) {
                        alert('安装成功！');
                        closeAppModal();
                        loadData();
                    } else {
                        alert('安装失败: ' + (installResult.detail || installResult.message));
                    }
                } else {
                    alert('上传失败: ' + (result.detail || result.message));
                }
            } catch(e) {
                alert('请求失败');
            }
        }

        loadData();
        setInterval(loadData, 5000);

        async function showLogs() {
            document.getElementById('logModal').style.display = 'block';
            const logs = await (await fetch('/api/v1/logs')).json();
            const logList = document.getElementById('logList');
            if (logs.length === 0) {
                logList.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">暂无操作记录</div>';
                return;
            }
            const actionMap = {
                'bind_policy': '策略绑定',
                'screenshot': '远程截屏',
                'adb_install': '安装APK',
                'uninstall': '卸载应用',
                'install_uploaded': '上传安装',
                'delete_policy': '删除策略',
                'delete_device': '移除设备'
            };
            logList.innerHTML = logs.map(log => `
                <div style="padding: 10px; border-bottom: 1px solid #eee;">
                    <div style="display: flex; justify-content: space-between; color: #666;">
                        <span style="color:#1a73e8">[${actionMap[log.action] || log.action}]</span>
                        <span>${log.created_at ? log.created_at.replace('T', ' ').substring(0, 19) : ''}</span>
                    </div>
                    <div style="margin-top: 5px;">${log.detail || ''}</div>
                    ${log.device_name ? `<div style="color:#999; font-size:0.8rem; margin-top:3px">设备: ${log.device_name}</div>` : ''}
                </div>
            `).join('');
        }

        function closeLogModal() {
            document.getElementById('logModal').style.display = 'none';
        }

        async function clearLogs() {
            if (!confirm('确定要清空所有操作日志吗？')) return;
            await fetch('/api/v1/logs', { method: 'DELETE' });
            showLogs();
        }
    </script>
</body>
</html>"""
with open(os.path.join(backend_templates_dir, "index.html"), 'w', encoding='utf-8') as f:
    f.write(enhanced_html)

print("Backend, UI, Screenshot and Detailed Network Info updated successfully.")
