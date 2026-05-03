import secrets
import os
import socket
import subprocess
import time
import asyncio
import base64
import json
from datetime import datetime, timedelta, timezone
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

from .db import Base, engine, get_db
from .models import Device, DeviceHeartbeat, Policy, OperationLog
from .schemas import DeviceHeartbeatIn, DeviceOut, DeviceRegister, PolicyCreate, PolicyOut, OperationLogOut

Base.metadata.create_all(bind=engine)

# 自动迁移：为旧数据库添加缺失的列
def _migrate_db():
    from sqlalchemy import inspect as sa_inspect, text
    insp = sa_inspect(engine)
    existing_cols = [c['name'] for c in insp.get_columns('devices')]
    new_columns = {
        'network_type': 'VARCHAR(16)',
        'wifi_rssi': 'INTEGER',
        'wifi_frequency': 'INTEGER',
        'wifi_link_speed': 'INTEGER',
        'ping_latency': 'INTEGER',
        'ping_packet_loss': 'INTEGER',
    }
    with engine.connect() as conn:
        for col_name, col_type in new_columns.items():
            if col_name not in existing_cols:
                conn.execute(text(f'ALTER TABLE devices ADD COLUMN {col_name} {col_type}'))
                conn.commit()
                print(f"[migration] Added column: devices.{col_name}")

_migrate_db()

def log_operation(db: Session, action: str, detail: str = None, device_id: int = None, device_name: str = None, operator: str = "admin"):
    log = OperationLog(action=action, detail=detail, device_id=device_id, device_name=device_name, operator=operator)
    db.add(log)
    db.commit()

def detect_server_url(tv_ip: str) -> str:
    """自动检测本机在TV同一子网上的IP地址，返回服务器URL"""
    try:
        # 获取本机所有IP地址
        hostname = socket.gethostname()
        local_ips = socket.gethostbyname_ex(hostname)[2]
        # 过滤掉127.x.x.x
        local_ips = [ip for ip in local_ips if not ip.startswith("127.")]

        # 找到与TV同一子网的IP
        tv_prefix = ".".join(tv_ip.split(".")[:3])
        for ip in local_ips:
            if ip.startswith(tv_prefix + "."):
                return f"http://{ip}:8000"

        # 如果没有同子网的IP，使用第一个非localhost的IP
        if local_ips:
            return f"http://{local_ips[0]}:8000"
    except Exception:
        pass
    return "http://localhost:8000"

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


def ensure_adb_server(adb_path: str) -> bool:
    """确保ADB server正在运行。如果未运行则尝试启动。"""
    try:
        result = subprocess.run([adb_path, "start-server"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False

app = FastAPI(title="Mi TV Launcher Backend", version="0.1.0")

# 项目根目录（backend_server/），基于本文件位置计算，不依赖CWD
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_latest_apk() -> str | None:
    """查找最新的APK文件，优先返回最近修改的，确保总是安装最新构建版本。
    搜索范围：构建输出目录 > 上传目录 > OTA目录
    """
    candidates = []
    project_root = os.path.dirname(BASE_DIR)  # tv-launcher-app/

    # 1. 构建输出（gradlew assembleDebug 生成）
    build_dir = os.path.join(project_root, "android_app", "app", "build", "outputs", "apk", "debug")
    if os.path.exists(build_dir):
        for f in os.listdir(build_dir):
            if f.endswith('.apk'):
                candidates.append(os.path.join(build_dir, f))

    # 2. 上传目录（手动上传的APK）
    upload_dir = os.path.join(BASE_DIR, "static", "uploads")
    if os.path.exists(upload_dir):
        for f in os.listdir(upload_dir):
            if f.endswith('.apk') and 'tvlauncher' in f.lower():
                candidates.append(os.path.join(upload_dir, f))

    # 3. OTA目录
    ota_dir = os.path.join(BASE_DIR, "static", "ota")
    if os.path.exists(ota_dir):
        for f in os.listdir(ota_dir):
            if f.endswith('.apk'):
                candidates.append(os.path.join(ota_dir, f))

    if not candidates:
        return None

    # 返回修改时间最新的APK
    return max(candidates, key=os.path.getmtime)


def adb_connect_and_verify(adb_path: str, ip: str, timeout: int = 15) -> dict:
    """连接ADB并验证shell可用性。
    策略：先检查现有连接是否可用，可用则直接返回；不可用时才断开重连。
    避免不必要的disconnect破坏已有的有效连接。
    返回 {"ok": bool, "detail": str}
    """
    addr = f"{ip}:5555"

    # 确保ADB server正在运行
    ensure_adb_server(adb_path)

    try:
        shell_res = subprocess.run(
            [adb_path, "-s", addr, "shell", "echo", "ok"],
            capture_output=True, text=True, timeout=8
        )
        if shell_res.stdout and shell_res.stdout.strip() == "ok":
            return {"ok": True, "detail": "ADB已连接且已授权"}

        # 现有连接不可用，分析原因
        stderr = (shell_res.stderr or "").lower()
        stdout_lower = (shell_res.stdout or "").lower()

        if "unauthorized" in stderr or "unauthorized" in stdout_lower:
            # 设备未授权，重连也解决不了，需要用户在电视上点击允许
            return {"ok": False, "detail": "ADB已连接但未授权，请在电视上点击「始终允许」"}
        if "offline" in stderr or "offline" in stdout_lower:
            # 设备离线，断开重连尝试恢复
            pass
        # 其他错误或没有连接，尝试重连

    except subprocess.TimeoutExpired:
        # shell超时，连接可能已死，需要重连
        pass
    except Exception:
        pass

    # 第二步：现有连接不可用，断开并重连
    try:
        subprocess.run([adb_path, "disconnect", addr], timeout=5, capture_output=True)
        time.sleep(0.5)

        conn_res = subprocess.run([adb_path, "connect", addr], capture_output=True, text=True, timeout=timeout)
        conn_output = (conn_res.stdout or "").lower()

        if "refused" in conn_output:
            return {"ok": False, "detail": "电视ADB未开启，需在电视上手动打开ADB调试"}
        if "failed" in conn_output and "connected" not in conn_output:
            return {"ok": False, "detail": "ADB无法连接，电视可能关机或断网"}

        # 连接成功，等待设备就绪
        time.sleep(1)

        # 验证shell可用性
        for attempt in range(3):
            shell_res = subprocess.run(
                [adb_path, "-s", addr, "shell", "echo", "ok"],
                capture_output=True, text=True, timeout=8
            )
            stdout = (shell_res.stdout or "").strip()
            stderr = (shell_res.stderr or "").lower()

            if stdout == "ok":
                return {"ok": True, "detail": "ADB已连接且已授权"}

            if "unauthorized" in stderr or "unauthorized" in stdout.lower():
                return {"ok": False, "detail": "ADB已连接但未授权，请在电视上点击「始终允许」"}
            if "offline" in stderr or "offline" in stdout.lower():
                if attempt < 2:
                    time.sleep(2)
                    continue
                return {"ok": False, "detail": "电视ADB处于离线状态，请尝试重启电视或重新连接"}

            if attempt < 2:
                time.sleep(2)

        return {"ok": False, "detail": f"ADB已连接但无法操作: {stderr[:60] or stdout[:60]}"}

    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": "ADB连接超时，电视可能卡顿或网络不稳定"}
    except Exception as e:
        return {"ok": False, "detail": f"ADB连接异常: {e}"}

@app.on_event("startup")
def list_routes():
    for route in app.routes:
        methods = getattr(route, "methods", ["MOUNT"])
        print(f"Route: {route.path} [ {','.join(methods)} ]")

# ========== 心跳超时离线检测 ==========
OFFLINE_TIMEOUT_MINUTES = 30  # 超过30分钟无心跳则标记离线
OFFLINE_CHECK_INTERVAL = 60   # 每60秒检查一次

async def check_offline_devices():
    """后台定时任务：将超时无心跳的在线设备标记为离线"""
    while True:
        await asyncio.sleep(OFFLINE_CHECK_INTERVAL)
        try:
            from .db import SessionLocal
            db = SessionLocal()
            timeout = datetime.now(timezone.utc) - timedelta(minutes=OFFLINE_TIMEOUT_MINUTES)
            stale_devices = db.query(Device).filter(
                and_(Device.online == True, Device.updated_at < timeout)
            ).all()
            for d in stale_devices:
                d.online = False
                d.wifi_rssi = None
                d.wifi_frequency = None
                d.wifi_link_speed = None
                d.ping_latency = None
                d.ping_packet_loss = None
                print(f"[离线检测] {d.device_name} 超过{OFFLINE_TIMEOUT_MINUTES}分钟无心跳，标记为离线")
            if stale_devices:
                db.commit()
            db.close()
        except Exception as e:
            print(f"[离线检测] 错误: {e}")

@app.on_event("startup")
async def start_offline_checker():
    asyncio.create_task(check_offline_devices())
    print(f"[离线检测] 已启动，超时={OFFLINE_TIMEOUT_MINUTES}分钟，检查间隔={OFFLINE_CHECK_INTERVAL}秒")

# Ensure directories exist
for path in ["static/ota", "static/screenshots", "static/uploads", "app/templates"]:
    full_path = os.path.join(BASE_DIR, path)
    if not os.path.exists(full_path):
        os.makedirs(full_path)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

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
            # 只更新非None的字段，避免APP不上报的字段（如room_name）覆盖已有值
            if value is not None:
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
        raise HTTPException(status_code=401, detail="设备令牌无效")
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
            # 清洗无效 SSID 值（小米电视通过有线连接时可能返回 "0x" 等垃圾值）
            if key == "network_ssid" and value in ("0x", "0x0", "<unknown ssid>"):
                value = "未连接"
            # 当活动网络为有线时，清洗WiFi SSID中的垃圾值
            if key == "network_ssid" and update_data.get("network_type") == "ethernet" and value not in ("未连接", None):
                # WiFi可能仍然连接着（小米电视特性），但SSID不应作为主要显示
                pass  # 保留SSID，前端会优先显示network_type
            setattr(device, key, value)
    
    device.online = True
    # Fetch android_version if not yet known
    if not device.android_version:
        ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
        if ip and ip != "0.0.0.0":
            try:
                adb_path = resolve_adb_path()
                subprocess.run([adb_path, "connect", f"{ip}:5555"], timeout=3, capture_output=True)
                result = subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "getprop", "ro.build.version.release"],
                                       capture_output=True, text=True, timeout=5)
                version = result.stdout.strip()
                if version:
                    device.android_version = version
            except Exception:
                pass
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
        },
        "policy_paused": device.policy_paused
    }

def push_policy_update_to_device(device: Device, db: Session, action_type: str = "policy_update"):
    """通过ADB推送策略更新到设备（包括暂停/恢复状态）"""
    try:
        ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
        if ip and ip != "0.0.0.0":
            adb_path = resolve_adb_path()
            # 连接ADB
            subprocess.run([adb_path, "connect", f"{ip}:5555"], timeout=5, capture_output=True)
            # 启动APP
            subprocess.run([
                adb_path, "-s", f"{ip}:5555", "shell",
                "am start -n com.company.tvlauncher/.MainActivity"
            ], timeout=5, capture_output=True)
            # 发送广播通知策略更新
            subprocess.run([
                adb_path, "-s", f"{ip}:5555", "shell",
                "am broadcast -a com.company.tvlauncher.POLICY_UPDATED"
            ], timeout=5, capture_output=True)
            log_operation(db, f"push_{action_type}", f"已推送{action_type}到 {device.device_name}", device.id, device.device_name)
            return True
    except Exception as e:
        log_operation(db, f"push_{action_type}_failed", f"推送失败: {str(e)}", device.id, device.device_name)
        return False
    return False

@app.post("/api/v1/devices/{device_id}/pause-policy")
def pause_policy(device_id: int, db: Session = Depends(get_db)):
    """暂停设备的策略执行"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")
    device.policy_paused = True
    db.commit()
    log_operation(db, "pause_policy", f"设备 {device.device_name} 的策略已暂停", device_id, device.device_name)
    # 实时推送到设备
    push_policy_update_to_device(device, db, "pause_policy")
    return {"ok": True, "policy_paused": True}

@app.post("/api/v1/devices/{device_id}/resume-policy")
def resume_policy(device_id: int, db: Session = Depends(get_db)):
    """恢复设备的策略执行"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")
    device.policy_paused = False
    db.commit()
    log_operation(db, "resume_policy", f"设备 {device.device_name} 的策略已恢复", device_id, device.device_name)
    # 实时推送到设备
    push_policy_update_to_device(device, db, "resume_policy")
    return {"ok": True, "policy_paused": False}

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
        raise HTTPException(status_code=404, detail="设备未找到")
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

@app.get("/api/v1/deploy-tv-stream")
def remote_deploy_stream(ip: str, server_url: str = None, db: Session = Depends(get_db)):
    """SSE stream version of deploy-tv, pushes real-time progress for each step."""
    import json as _json

    def sse(data: dict) -> str:
        return f"data: {_json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        adb_path = resolve_adb_path()
        if not server_url:
            _server_url = detect_server_url(ip)
        else:
            _server_url = server_url

        apk_path = find_latest_apk()
        if not apk_path:
            yield sse({"step": "error", "detail": "未找到安装包，请确保项目已编译或上传APK。"})
            return

        try:
            # Step 1: ADB connect
            yield sse({"step": "adb_connect", "message": "正在连接ADB..."})
            conn = adb_connect_and_verify(adb_path, ip)
            if not conn["ok"]:
                # 如果首次连接失败，可能需要等待授权，尝试重试
                auth_ok = False
                if "未授权" in conn["detail"]:
                    yield sse({"step": "adb_auth", "message": "等待电视授权（1/3）...请在电视上点击「始终允许」"})
                    for attempt in range(2):
                        time.sleep(5)
                        conn = adb_connect_and_verify(adb_path, ip)
                        if conn["ok"]:
                            auth_ok = True
                            break
                        yield sse({"step": "adb_auth", "message": f"等待电视授权（{attempt+2}/3）...请在电视上点击「始终允许」"})
                    if not auth_ok:
                        yield sse({"step": "error", "detail": "连接成功但未授权。请在电视上点击「始终允许」后重新部署。"})
                        return
                else:
                    yield sse({"step": "error", "detail": conn["detail"]})
                    return

            yield sse({"step": "adb_ok", "message": "ADB连接并授权成功"})

            # Step 2: Install APK
            yield sse({"step": "install_apk", "message": "正在清理旧数据..."})
            subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "pm", "clear", "com.company.tvlauncher"], timeout=10, capture_output=True)

            yield sse({"step": "install_apk", "message": "正在安装APP（约30秒）..."})
            install_res = subprocess.run([adb_path, "-s", f"{ip}:5555", "install", "-r", apk_path], capture_output=True, text=True, timeout=120)
            if install_res.returncode != 0:
                yield sse({"step": "error", "detail": f"安装失败: {install_res.stderr or install_res.stdout}"})
                return

            yield sse({"step": "install_ok", "message": "APP安装成功"})

            # Step 3: Uninstall bloatware
            yield sse({"step": "uninstall_bloat", "message": "正在获取已安装应用列表..."})
            addr = f"{ip}:5555"
            try:
                pkg_list_res = subprocess.run([adb_path, "-s", addr, "shell", "pm", "list", "packages"],
                                               capture_output=True, text=True, timeout=10)
                all_packages = set()
                for line in pkg_list_res.stdout.splitlines():
                    if line.startswith("package:"):
                        all_packages.add(line.replace("package:", "").strip())
            except Exception:
                all_packages = set()

            uninstalled = []
            skipped_count = 0
            for pkg in AD_BLOCKLIST:
                if pkg in all_packages:
                    try:
                        yield sse({"step": "uninstall_bloat", "message": f"正在卸载 {pkg.split('.')[-1]}..."})
                        res = subprocess.run([adb_path, "-s", addr, "shell", "pm", "uninstall", "--user", "0", pkg],
                                             capture_output=True, text=True, timeout=10)
                        if "Success" in res.stdout:
                            uninstalled.append(pkg)
                        else:
                            skipped_count += 1
                    except Exception:
                        skipped_count += 1
                else:
                    skipped_count += 1

            # 清除小米桌面数据，确保不会弹出默认桌面选择
            subprocess.run([adb_path, "-s", addr, "shell", "pm", "clear", "com.xiaomi.mitv.tvhome"],
                           capture_output=True, text=True, timeout=5)

            yield sse({"step": "uninstall_bloat_ok", "message": f"已卸载{len(uninstalled)}个预装应用"})

            # Step 4: Configure & Launch
            yield sse({"step": "configure", "message": "正在配置服务器地址..."})
            subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "am", "force-stop", "com.company.tvlauncher"], timeout=5)
            time.sleep(1)
            subprocess.run([adb_path, "-s", f"{ip}:5555", "shell",
                           "settings", "put", "global", "tv_launcher_server_url", _server_url], timeout=10)

            yield sse({"step": "launch", "message": "正在启动APP..."})
            subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "am", "start", "-n", "com.company.tvlauncher/.MainActivity"], timeout=15)

            yield sse({"step": "wait_register", "message": "等待APP自注册（约10秒）..."})
            time.sleep(10)

            # Find device
            device = db.query(Device).filter(
                (Device.eth_ip == ip) | (Device.wifi_ip == ip)
            ).first()

            if not device:
                yield sse({"step": "done", "ok": True, "message": f"APP已安装并启动，设备将自动注册到 {_server_url}"})
                return

            # Bind default policy
            existing_policy = db.query(Policy).first()
            if not existing_policy:
                default_policy = Policy(
                    name="默认策略", mode="app", target_app_package="com.android.settings",
                    target_hdmi_port=1, fallback_mode="app", fallback_value="com.android.settings", is_active=True
                )
                db.add(default_policy)
                db.commit()
                db.refresh(default_policy)

            if device.policy_id is None:
                default_policy = db.query(Policy).filter(Policy.name == "默认策略").first()
                if default_policy:
                    device.policy_id = default_policy.id
                    db.commit()

            log_operation(db, "deploy_success", f"已成功向 {ip} 部署 Launcher", device.id, device.device_name)
            yield sse({"step": "done", "ok": True, "message": f"部署成功！设备 {device.device_name} 已上线", "device_id": device.id, "device_name": device.device_name})

        except Exception as e:
            yield sse({"step": "error", "detail": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/v1/devices/{device_id}/bind-policy/{policy_id}")
def bind_policy(device_id: int, policy_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not device or not policy:
        raise HTTPException(status_code=404, detail="设备或策略未找到")
    device.policy_id = policy.id
    db.commit()
    log_operation(db, "bind_policy", f"设备 {device.device_name} 绑定了策略 {policy.name}", device_id, device.device_name)

    # 通过ADB推送策略更新到设备
    try:
        ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
        if ip and ip != "0.0.0.0":
            adb_path = resolve_adb_path()
            # 连接ADB
            subprocess.run([adb_path, "connect", f"{ip}:5555"], timeout=5, capture_output=True)
            # 启动APP
            subprocess.run([
                adb_path, "-s", f"{ip}:5555", "shell",
                "am start -n com.company.tvlauncher/.MainActivity"
            ], timeout=5, capture_output=True)
            # 发送广播
            subprocess.run([
                adb_path, "-s", f"{ip}:5555", "shell",
                "am broadcast -a com.company.tvlauncher.POLICY_UPDATED"
            ], timeout=5, capture_output=True)
            log_operation(db, "policy_push", f"已推送策略更新到 {device.device_name}", device_id, device.device_name)
    except Exception as e:
        log_operation(db, "policy_push_failed", f"推送失败: {str(e)}", device_id, device.device_name)

    return {"ok": True}

@app.post("/api/v1/devices/{device_id}/room")
def update_room(device_id: int, room_name: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")
    old_room = device.room_name
    device.room_name = room_name
    db.commit()
    log_operation(db, "update_room", f"设备 {device.device_name} 的会议室从 {old_room} 改为 {room_name}", device_id, device.device_name)
    return {"ok": True}

@app.get("/api/v1/devices/{device_id}/screenshot")
def get_screenshot(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")

    adb_path = resolve_adb_path()
    local_path = os.path.join(BASE_DIR, f"static/screenshots/device_{device_id}.png")
    
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
        os.path.join(BASE_DIR, "scrcpy", "scrcpy.exe"),  # Windows
        os.path.join(BASE_DIR, "scrcpy", "scrcpy"),      # Linux/macOS
    ]

    for path in project_scrcpy_paths:
        if os.path.exists(path):
            return path

    # 如果未找到，尝试自动安装
    print("Scrcpy未找到，尝试自动安装...")
    install_script = os.path.join(BASE_DIR, "install_scrcpy.py")
    
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

@app.post("/api/v1/scrcpy/auto-install")
async def auto_install_scrcpy():
    """自动下载安装Scrcpy"""
    import sys as _sys
    install_script = os.path.join(BASE_DIR, "install_scrcpy.py")
    if not os.path.exists(install_script):
        return {"ok": False, "detail": "Scrcpy安装脚本未找到"}
    try:
        result = subprocess.run(
            [_sys.executable, install_script],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            # Check again
            path = get_scrcpy_path()
            if path:
                return {"ok": True, "path": path, "message": "Scrcpy安装成功"}
            else:
                return {"ok": False, "detail": "安装完成但未找到可执行文件"}
        else:
            return {"ok": False, "detail": result.stderr[-500:] if result.stderr else "安装失败"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": "安装超时（5分钟）"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

@app.get("/api/v1/scrcpy/download-script")
async def download_scrcpy_setup_script():
    """生成其他电脑的一键安装Scrcpy脚本（.bat）"""
    script = '''@echo off
chcp 65001 >nul 2>&1
title Install Scrcpy + ADB
echo ========================================
echo   Scrcpy + ADB Auto Installer
echo ========================================
echo.

:: 1. Create folder
set "INSTALL_DIR=%USERPROFILE%\\scrcpy"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
cd /d "%INSTALL_DIR%"

:: 2. Download ADB
echo [1/3] Downloading ADB...
if not exist "adb.exe" (
    curl -L -o platform-tools.zip "https://dl.google.com/android/repository/platform-tools-latest-windows.zip" --timeout 60
    if errorlevel 1 (
        echo [ERROR] Failed to download ADB
        pause
        exit /b 1
    )
    powershell -command "Expand-Archive -Path platform-tools.zip -DestinationPath . -Force"
    copy platform-tools\\adb.exe . >nul
    copy platform-tools\\AdbWinApi.dll . >nul
    copy platform-tools\\AdbWinUsbApi.dll . >nul
    del platform-tools.zip
    rmdir /s /q platform-tools
    echo   ADB OK
) else (
    echo   ADB already exists
)

:: 3. Download Scrcpy
echo [2/3] Downloading Scrcpy v2.4...
if not exist "scrcpy.exe" (
    curl -L -o scrcpy.zip "https://github.com/Genymobile/scrcpy/releases/download/v2.4/scrcpy-win64-v2.4.zip" --timeout 120
    if errorlevel 1 (
        echo [ERROR] Failed to download Scrcpy
        echo   Please download manually from:
        echo   https://github.com/Genymobile/scrcpy/releases
        pause
        exit /b 1
    )
    powershell -command "Expand-Archive -Path scrcpy.zip -DestinationPath . -Force"
    move scrcpy-win64-v2.4\\scrcpy.exe . >nul 2>&1
    xcopy scrcpy-win64-v2.4\\*.dll . /Y >nul 2>&1
    if exist scrcpy-win64-v2.4\\share xcopy scrcpy-win64-v2.4\\share share\\ /E /Y /I >nul 2>&1
    del scrcpy.zip
    rmdir /s /q scrcpy-win64-v2.4
    echo   Scrcpy OK
) else (
    echo   Scrcpy already exists
)

:: 4. Add to PATH
echo [3/3] Adding to PATH...
setx PATH "%PATH%;%INSTALL_DIR%" >nul 2>&1
set "PATH=%PATH%;%INSTALL_DIR%"

echo.
echo ========================================
echo   Install complete!
echo   Location: %INSTALL_DIR%
echo.
echo   Usage:
echo     adb connect TV_IP:5555
echo     scrcpy -s TV_IP:5555
echo ========================================
echo.
pause
'''
    from fastapi.responses import Response
    return Response(
        content=script,
        media_type="application/bat",
        headers={"Content-Disposition": "attachment; filename=install_scrcpy.bat"}
    )

@app.post("/api/v1/devices/{device_id}/scrcpy/start")
async def start_scrcpy_session(device_id: int, db: Session = Depends(get_db)):
    """启动Scrcpy远程控制会话"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")
    
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
    """通过ADB连接到设备，连接后验证shell可用性"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")

    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")

    adb_path = resolve_adb_path()
    result = adb_connect_and_verify(adb_path, ip)

    if result["ok"]:
        log_operation(db, "adb_connect", f"ADB连接成功: {ip}", device_id, device.device_name)
        return {"ok": True, "message": result["detail"]}
    else:
        log_operation(db, "adb_connect_failed", result["detail"], device_id, device.device_name)
        return {"ok": False, "detail": result["detail"]}

@app.post("/api/v1/devices/{device_id}/adb/disconnect")
async def adb_disconnect_device(device_id: int, db: Session = Depends(get_db)):
    """断开ADB连接"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")
    
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
        raise HTTPException(status_code=404, detail="设备未找到")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")
    
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
        raise HTTPException(status_code=404, detail="设备未找到")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")

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

@app.post("/api/v1/devices/{device_id}/adb/shell")
def adb_shell(device_id: int, command: str = "", db: Session = Depends(get_db)):
    """执行任意ADB命令并返回输出"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")

    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")

    if not command.strip():
        raise HTTPException(status_code=400, detail="命令不能为空")

    # 安全过滤：禁止危险命令
    dangerous_patterns = ["rm -rf /", "format", "mkfs", "dd if=", "> /dev/", "shutdown"]
    cmd_lower = command.lower()
    for pattern in dangerous_patterns:
        if pattern in cmd_lower:
            raise HTTPException(status_code=403, detail=f"禁止执行的命令模式: {pattern}")

    adb_path = resolve_adb_path()
    try:
        subprocess.run([adb_path, "connect", f"{ip}:5555"], timeout=5, capture_output=True)
        # 构建完整命令
        full_cmd = [adb_path, "-s", f"{ip}:5555"] + command.split()
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        return {"ok": True, "output": output.strip(), "exit_code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "命令执行超时(30秒)", "exit_code": -1}
    except Exception as e:
        return {"ok": False, "output": str(e), "exit_code": -1}

@app.post("/api/v1/scrcpy/connect-by-ip")
def scrcpy_connect_by_ip(ip: str):
    """通过IP直接连接ADB并启动scrcpy"""
    if not ip or ip.strip() == "":
        raise HTTPException(status_code=400, detail="IP地址不能为空")

    ip = ip.strip()
    adb_path = resolve_adb_path()
    try:
        # 连接ADB
        connect_result = subprocess.run(
            [adb_path, "connect", f"{ip}:5555"],
            capture_output=True, text=True, timeout=10
        )
        if "refused" in connect_result.stdout.lower() or "failed" in connect_result.stdout.lower():
            return {"ok": False, "message": f"ADB连接失败: {connect_result.stdout.strip()}"}

        # 启动scrcpy
        scrcpy_path = get_scrcpy_path()
        if not scrcpy_path:
            return {"ok": False, "message": "Scrcpy未安装，请先安装Scrcpy"}

        subprocess.Popen(
            [scrcpy_path, "--serial", f"{ip}:5555", "--no-audio", "--max-fps", "30", "--max-size", "1024", "--always-on-top"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return {"ok": True, "message": f"已连接 {ip}:5555 并启动Scrcpy"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "ADB连接超时"}
    except Exception as e:
        return {"ok": False, "message": str(e)}

@app.post("/api/v1/devices/{device_id}/adb-install")
def adb_install(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")
    
    adb_path = resolve_adb_path()
    # Search for APK in android_app folder
    apk_path = os.path.join(BASE_DIR, "..", "android_app", "app", "build", "outputs", "apk", "debug", "app-debug.apk")
    
    if not os.path.exists(apk_path):
        return {"ok": False, "detail": f"未找到APK安装包: {apk_path}"}

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

@app.post("/api/v1/devices/{device_id}/silent-upgrade")
def silent_upgrade(device_id: int, db: Session = Depends(get_db)):
    """静默升级管理应用到最新版本（不影响电视当前操作）
    使用 adb install -r 覆盖安装，APP正在运行时也能安装。
    安装完成后APP会自动恢复运行（保活服务+开机自启机制）。
    自动查找最新构建的APK文件进行安装。
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")

    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")

    adb_path = resolve_adb_path()
    latest_apk = find_latest_apk()

    if not latest_apk:
        return {"ok": False, "detail": "未找到APK文件，请先构建或上传APK"}

    try:
        # 1. 连接设备并验证
        conn = adb_connect_and_verify(adb_path, ip)
        if not conn["ok"]:
            return {"ok": False, "detail": conn["detail"]}

        # 2. 获取当前版本号（安装前）
        version_before = subprocess.run(
            [adb_path, "-s", f"{ip}:5555", "shell", "dumpsys", "package", "com.company.tvlauncher"],
            capture_output=True, text=True, timeout=10
        )
        old_version = ""
        for line in version_before.stdout.split('\n'):
            if 'versionName' in line:
                old_version = line.strip()
                break

        # 3. 静默覆盖安装（-r: 替换已有应用）
        result = subprocess.run(
            [adb_path, "-s", f"{ip}:5555", "install", "-r", latest_apk],
            capture_output=True, text=True, timeout=120
        )

        if result.returncode != 0:
            output = result.stderr or result.stdout
            # 如果覆盖安装失败，尝试先停止APP再安装
            if "INSTALL_FAILED" in output:
                subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "am", "force-stop", "com.company.tvlauncher"], timeout=5, capture_output=True)
                time.sleep(1)
                result = subprocess.run(
                    [adb_path, "-s", f"{ip}:5555", "install", "-r", latest_apk],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode != 0:
                    return {"ok": False, "detail": f"安装失败: {result.stderr or result.stdout}"}

        # 4. 安装成功后，APP会被系统自动重启（因为 persistent=true + 前台服务）
        # 稍等片刻让APP重启
        time.sleep(3)

        # 5. 确保APP已启动
        subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "am", "start", "-n", "com.company.tvlauncher/.MainActivity"], timeout=10, capture_output=True)

        apk_name = os.path.basename(latest_apk)
        apk_size = os.path.getsize(latest_apk) // 1024
        apk_mtime = datetime.fromtimestamp(os.path.getmtime(latest_apk)).strftime("%Y-%m-%d %H:%M")
        log_operation(db, "silent_upgrade", f"静默升级 {device.device_name}，APK: {apk_name} ({apk_size}KB, 构建: {apk_mtime})", device_id, device.device_name)
        return {"ok": True, "message": f"升级成功！APK: {apk_name} ({apk_size}KB, 构建时间: {apk_mtime})，应用已自动重启"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": "安装超时（设备可能不响应）"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

@app.post("/api/v1/devices/{device_id}/uninstall")
def uninstall_app(device_id: int, package_name: str, is_system: bool = False, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")

    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")

    adb_path = resolve_adb_path()

    try:
        subprocess.run([adb_path, "connect", ip], timeout=5)
        if is_system:
            # System app: use pm uninstall --user 0 (disable for current user)
            result = subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "pm", "uninstall", "--user", "0", package_name], capture_output=True, text=True, timeout=30)
        else:
            # Normal app: use pm uninstall (full uninstall)
            result = subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "pm", "uninstall", package_name], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"ok": False, "detail": result.stderr or result.stdout}
        # Check output for common failure patterns
        output = (result.stdout or "") + (result.stderr or "")
        if "DELETE_FAILED_INTERNAL_ERROR" in output:
            return {"ok": False, "detail": "系统应用无法完全卸载，请使用冻结功能"}
        log_operation(db, "uninstall", f"从设备 {device.device_name} 卸载应用 {package_name}{'(系统应用)' if is_system else ''}", device_id, device.device_name)
        return {"ok": True, "message": "卸载成功" if not is_system else "已停用该系统应用（恢复出厂设置可恢复）"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

# 一键部署：安装APK + 卸载广告应用 + 设置默认HOME
AD_BLOCKLIST = [
    "com.xiaomi.mitv.upgrade",
    "com.xiaomi.mitv.tvpush.tvpushservice",
    "com.miui.analytics",
    "com.miui.tv.analytics",
    "com.miui.mitv.shoplugin",
    "com.xiaomi.mitv.appstore",
    "com.mitv.screensaver",
    "com.mitv.tvhome",
    "com.xiaomi.tv.gallery",
    "com.yangqi.rom.launcher.free",
    "com.xiaomi.mitv.settings2",
    "com.xiaomi.hyperos.tv.settings",
    "com.xiaomi.mitv.settings",
    "com.mitv.settings",
    "com.duokan.videodaily",
    "com.xiaomi.mitv.shop",
    "com.xiaomi.mitv.calendar",
    "com.xiaomi.mitv.handbook",
    "com.xiaomi.mitv.karaoke.service",
    "com.mitv.gallery",
    "com.xiaomi.mitv.healthdiagnosis",
    "com.mi.miplay.mitvupnpsink",
    "com.xiaomi.mitv.smartshare",
    "com.xm.webcontent",
    "com.mitv.shoplugin",
    "com.xiaomi.mitv.mediaexplorer",
    "com.xiaomi.mibox.gamecenter",
]

@app.post("/api/v1/devices/{device_id}/one-click-deploy")
def one_click_deploy(device_id: int, db: Session = Depends(get_db)):
    """一键部署：检查ADB连接 → 安装APK → 卸载广告应用 → 设置默认HOME"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")

    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        return {"ok": False, "step": "check_ip", "detail": "设备没有IP地址，请先确认电视已联网"}

    adb_path = resolve_adb_path()
    addr = f"{ip}:5555"
    logs = []

    # Step 1: ADB connect
    try:
        conn = subprocess.run([adb_path, "connect", addr], capture_output=True, text=True, timeout=10)
        logs.append(f"[连接] {conn.stdout.strip()}")
    except Exception as e:
        return {"ok": False, "step": "adb_connect", "detail": f"ADB连接失败: {e}", "logs": logs}

    # Step 2: Verify connection
    try:
        check = subprocess.run([adb_path, "-s", addr, "shell", "echo", "ok"], capture_output=True, text=True, timeout=5)
        if "ok" not in check.stdout:
            return {"ok": False, "step": "adb_auth", "detail": "ADB未授权，请在电视上点击「允许」按钮", "logs": logs}
        logs.append("[验证] ADB连接成功")
    except Exception as e:
        return {"ok": False, "step": "adb_auth", "detail": f"ADB未连接或未授权，请在电视上点击「允许」: {e}", "logs": logs}

    # Step 3: Get installed packages for smart matching
    try:
        pkg_list = subprocess.run([adb_path, "-s", addr, "shell", "pm", "list", "packages", "-3"],
                                  capture_output=True, text=True, timeout=10)
        system_pkg_list = subprocess.run([adb_path, "-s", addr, "shell", "pm", "list", "packages", "-s"],
                                         capture_output=True, text=True, timeout=10)
        all_packages = set()
        for line in (pkg_list.stdout + system_pkg_list).splitlines():
            if line.startswith("package:"):
                all_packages.add(line.replace("package:", "").strip())
    except Exception:
        all_packages = set()

    # Step 4: Install APK
    apk_path = os.path.join(BASE_DIR, "..", "android_app", "app", "build", "outputs", "apk", "debug", "app-debug.apk")
    if not os.path.exists(apk_path):
        return {"ok": False, "step": "find_apk", "detail": "未找到APK安装包", "logs": logs}

    try:
        install_res = adb_silent_install(adb_path, addr, apk_path)
        if install_res.returncode != 0 or "Failure" in (install_res.stdout or ""):
            logs.append(f"[安装] 失败: {install_res.stdout} {install_res.stderr}")
            return {"ok": False, "step": "install_apk", "detail": f"APK安装失败: {install_res.stdout or install_res.stderr}", "logs": logs}
        logs.append("[安装] APK安装成功")
    except Exception as e:
        return {"ok": False, "step": "install_apk", "detail": f"APK安装异常: {e}", "logs": logs}

    # Step 5: Uninstall ad/bloat apps (smart match)
    uninstalled = []
    skipped = []
    for pkg in AD_BLOCKLIST:
        if pkg in all_packages:
            try:
                res = subprocess.run([adb_path, "-s", addr, "shell", "pm", "uninstall", "--user", "0", pkg],
                                     capture_output=True, text=True, timeout=10)
                if "Success" in res.stdout:
                    uninstalled.append(pkg)
                    logs.append(f"[卸载] {pkg} - 成功")
                else:
                    skipped.append(f"{pkg}({res.stdout.strip()})")
                    logs.append(f"[卸载] {pkg} - 跳过: {res.stdout.strip()}")
            except Exception:
                skipped.append(f"{pkg}(超时)")
                logs.append(f"[卸载] {pkg} - 超时")
        else:
            skipped.append(f"{pkg}(未安装)")

    logs.append(f"[卸载] 共卸载{len(uninstalled)}个应用，跳过{len(skipped)}个")

    # Step 6: Set as default HOME
    try:
        subprocess.run([adb_path, "-s", addr, "shell",
                        "pm", "clear", "com.xiaomi.mitv.tvhome"], capture_output=True, text=True, timeout=5)
        subprocess.run([adb_path, "-s", addr, "shell",
                        "settings", "put", "global", "preferred_launcher", "com.company.tvlauncher"],
                       capture_output=True, text=True, timeout=5)
        logs.append("[设置] 已设置默认启动器")
    except Exception as e:
        logs.append(f"[设置] 设置默认启动器失败(可手动设置): {e}")

    # Step 7: Launch the app
    try:
        subprocess.run([adb_path, "-s", addr, "shell",
                        "am", "start", "-n", "com.company.tvlauncher/.MainActivity"],
                       capture_output=True, text=True, timeout=10)
        logs.append("[启动] Launcher已启动")
    except Exception:
        logs.append("[启动] 启动Launcher失败(重启电视即可)")

    log_operation(db, "one_click_deploy", f"一键部署完成: 安装APK+卸载{len(uninstalled)}个应用", device_id, device.device_name)
    return {
        "ok": True,
        "uninstalled": uninstalled,
        "uninstalled_count": len(uninstalled),
        "skipped_count": len(skipped),
        "logs": logs
    }

@app.post("/api/v1/devices/{device_id}/check-adb")
def check_adb(device_id: int, db: Session = Depends(get_db)):
    """检查设备的ADB连接状态"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")

    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        return {"connected": False, "authorized": False, "detail": "设备没有IP地址"}

    adb_path = resolve_adb_path()
    result = adb_connect_and_verify(adb_path, ip)

    return {
        "connected": result["ok"],
        "authorized": result["ok"],
        "detail": result["detail"]
    }

@app.post("/api/v1/devices/{device_id}/launch-app")
def launch_app(device_id: int, package_name: str, db: Session = Depends(get_db)):
    """通过ADB启动指定应用"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")

    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")

    adb_path = resolve_adb_path()

    try:
        subprocess.run([adb_path, "connect", ip], timeout=5)
        # Use monkey command to launch app's main activity reliably
        result = subprocess.run(
            [adb_path, "-s", f"{ip}:5555", "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            # Fallback: try am start with main activity
            result2 = subprocess.run(
                [adb_path, "-s", f"{ip}:5555", "shell", "am", "start", "-n", f"{package_name}/.MainActivity"],
                capture_output=True, text=True, timeout=15
            )
            if result2.returncode != 0:
                return {"ok": False, "detail": result2.stderr or result2.stdout or "启动失败"}
        log_operation(db, "launch_app", f"在设备 {device.device_name} 启动应用 {package_name}", device_id, device.device_name)
        return {"ok": True, "message": f"已启动 {package_name}"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

@app.post("/api/v1/devices/{device_id}/enable-app")
def enable_app(device_id: int, package_name: str, db: Session = Depends(get_db)):
    """通过ADB重新启用已停用的应用（pm install-existing）"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")

    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")

    adb_path = resolve_adb_path()
    try:
        subprocess.run([adb_path, "connect", ip], timeout=5)
        # pm install-existing restores app for current user
        result = subprocess.run(
            [adb_path, "-s", f"{ip}:5555", "shell", "pm", "install-existing", package_name],
            capture_output=True, text=True, timeout=15
        )
        output = (result.stdout or "") + (result.stderr or "")
        if "Success" in output or result.returncode == 0:
            log_operation(db, "enable_app", f"在设备 {device.device_name} 重新启用应用 {package_name}", device_id, device.device_name)
            return {"ok": True, "message": f"已启用 {package_name}"}
        return {"ok": False, "detail": output.strip() or "启用失败"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

@app.post("/api/v1/adb/shell-by-ip")
def adb_shell_by_ip(ip: str, command: str = ""):
    """直接通过IP执行ADB命令（无需设备在数据库中）"""
    if not ip.strip():
        raise HTTPException(status_code=400, detail="IP不能为空")
    if not command.strip():
        raise HTTPException(status_code=400, detail="命令不能为空")

    dangerous_patterns = ["rm -rf /", "format", "mkfs", "dd if=", "> /dev/", "shutdown"]
    cmd_lower = command.lower()
    for pattern in dangerous_patterns:
        if pattern in cmd_lower:
            raise HTTPException(status_code=403, detail=f"禁止执行的命令模式: {pattern}")

    adb_path = resolve_adb_path()
    try:
        subprocess.run([adb_path, "connect", f"{ip}:5555"], timeout=5, capture_output=True)
        full_cmd = [adb_path, "-s", f"{ip}:5555"] + command.split()
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        return {"ok": True, "output": output.strip(), "exit_code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "命令执行超时(30秒)", "exit_code": -1}
    except Exception as e:
        return {"ok": False, "output": str(e), "exit_code": -1}

@app.post("/api/v1/devices/{device_id}/install-uploaded")
def install_uploaded(device_id: int, filename: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")

    adb_path = resolve_adb_path()
    apk_path = os.path.join(BASE_DIR, f"static/uploads/{filename}")
    
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
    
    upload_dir = os.path.join(BASE_DIR, "static", "uploads")
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
        with open(os.path.join(BASE_DIR, "app/templates/index.html"), "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "<h1>Dashboard Template Missing</h1>"

@app.delete("/api/v1/policies/{policy_id}")
def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="策略未找到")
    policy_name = policy.name
    db.delete(policy)
    db.commit()
    log_operation(db, "delete_policy", f"删除了策略: {policy_name}")
    return {"ok": True}

@app.delete("/api/v1/devices/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")
    device_name = device.device_name
    device_ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip

    # 通过ADB通知TV APP注销（清除本地token，防止自动重新注册）
    if device_ip and device_ip != "0.0.0.0":
        try:
            adb_path = resolve_adb_path()
            subprocess.run([adb_path, "connect", f"{device_ip}:5555"], timeout=5, capture_output=True)
            # 1. 先强制停止APP
            subprocess.run([adb_path, "-s", f"{device_ip}:5555", "shell",
                           "am force-stop com.company.tvlauncher"], timeout=5, capture_output=True)
            # 2. 卸载APP
            result = subprocess.run([adb_path, "-s", f"{device_ip}:5555", "shell",
                           "pm uninstall com.company.tvlauncher"], timeout=15, capture_output=True, text=True)
            uninstall_ok = "Success" in (result.stdout or "")
            if not uninstall_ok:
                # 卸载失败时尝试清除数据
                subprocess.run([adb_path, "-s", f"{device_ip}:5555", "shell",
                               "pm clear com.company.tvlauncher"], timeout=10, capture_output=True)
            log_operation(db, "deregister_device", f"已通过ADB卸载设备APP: {device_name} (卸载{'成功' if uninstall_ok else '失败，已清除数据'})", device_id, device_name)
        except Exception as e:
            log_operation(db, "deregister_device_failed", f"ADB注销失败(设备可能离线): {str(e)}", device_id, device_name)

    db.delete(device)
    db.commit()
    log_operation(db, "delete_device", f"移除了设备: {device_name}", device_id, device_name)
    return {"ok": True}

@app.get("/api/v1/devices/connectivity-check")
def connectivity_check(db: Session = Depends(get_db)):
    """批量检测所有设备的 ping 和 ADB 连通状态（并行检测，快速返回）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    devices = db.query(Device).all()
    adb_path = resolve_adb_path()
    results = {}

    def check_device(device):
        ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
        if not ip or ip == "0.0.0.0":
            return device.id, {"ping": False, "adb": False, "reason": "无IP"}

        # Ping check
        ping_ok = False
        try:
            ping_cmd = ["ping", "-n", "1", "-w", "1500", ip] if os.name == "nt" else ["ping", "-c", "1", "-W", "2", ip]
            ping_result = subprocess.run(ping_cmd, capture_output=True, text=True, timeout=3)
            ping_ok = ping_result.returncode == 0
        except Exception:
            pass

        # ADB check (only if ping is ok)
        adb_ok = False
        adb_reason = ""
        if ping_ok:
            try:
                result = adb_connect_and_verify(adb_path, ip)
                if result["ok"]:
                    adb_ok = True
                else:
                    adb_reason = result["detail"]
            except Exception:
                adb_reason = "ADB检测出错，请稍后重试"
        else:
            adb_reason = "网络不通，电视可能关机或断网"

        return device.id, {"ping": ping_ok, "adb": adb_ok, "reason": adb_reason}

    # 并行检测所有设备
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(check_device, d): d for d in devices}
        for future in as_completed(futures):
            try:
                dev_id, result = future.result(timeout=10)
                results[dev_id] = result
            except Exception as e:
                dev = futures[future]
                results[dev.id] = {"ping": False, "adb": False, "reason": str(e)[:30]}

    # 根据检测结果更新数据库中的 online 状态
    updated = False
    for device in devices:
        conn = results.get(device.id)
        if not conn:
            continue
        # ping 通即视为网络在线；ping 不通则离线
        new_online = conn["ping"]
        if device.online != new_online:
            device.online = new_online
            if not new_online:
                device.wifi_rssi = None
                device.wifi_frequency = None
                device.wifi_link_speed = None
                device.ping_latency = None
                device.ping_packet_loss = None
            updated = True
            print(f"[连通性检测] {device.device_name} online: {device.online} -> {new_online}")
    if updated:
        db.commit()

    return results

@app.get("/api/v1/logs", response_model=list[OperationLogOut])
def list_logs(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(OperationLog).order_by(OperationLog.id.desc()).limit(limit).all()

@app.delete("/api/v1/logs")
def clear_logs(db: Session = Depends(get_db)):
    db.query(OperationLog).delete()
    db.commit()
    return {"ok": True}

@app.get("/api/v1/ota/check")
def ota_check(version: str = "0.0.0", host: str = Header(default="localhost:8000")):
    latest_version = "0.1.5"
    if version < latest_version:
        # 使用请求的host构建下载URL，确保TV能访问到
        scheme_host = f"http://{host}" if not host.startswith("http") else host
        return {
            "update_available": True,
            "latest_version": latest_version,
            "url": f"{scheme_host}/static/ota/app-debug.apk",
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
        raise HTTPException(status_code=404, detail="设备未找到")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")
    
    adb_path = resolve_adb_path()
    local_path = os.path.join(BASE_DIR, f"static/screenshots/device_{device_id}_stream.png")
    
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
        
        return {"ok": True, "message": "截图已捕获并发送"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

# 鼠标控制端点
@app.post("/api/v1/devices/{device_id}/mouse")
async def mouse_control(device_id: int, action: str, x: int = None, y: int = None, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备未找到")
    
    ip = device.eth_ip if device.eth_ip and device.eth_ip != "0.0.0.0" else device.wifi_ip
    if not ip or ip == "0.0.0.0":
        raise HTTPException(status_code=400, detail="设备没有可用于ADB连接的IP地址")
    
    adb_path = resolve_adb_path()
    
    try:
        subprocess.run([adb_path, "connect", ip], timeout=5)
        
        if action == "tap":
            if x is not None and y is not None:
                subprocess.run([adb_path, "-s", f"{ip}:5555", "shell", "input", "tap", str(x), str(y)], check=True, timeout=5)
                log_operation(db, "mouse_tap", f"点击位置 ({x}, {y})", device_id, device.device_name)
                return {"ok": True, "message": f"已点击 ({x}, {y})"}
            else:
                return {"ok": False, "detail": "缺少 x 或 y 坐标"}
        
        elif action == "swipe":
            # 需要起始点和结束点
            return {"ok": False, "detail": "滑动操作需要起始和结束坐标"}
        
        elif action == "drag":
            # 拖拽操作
            return {"ok": False, "detail": "拖拽操作需要起始和结束坐标"}
        
        else:
            return {"ok": False, "detail": f"未知操作: {action}"}

    except Exception as e:
        return {"ok": False, "detail": str(e)}


@app.get("/api/v1/deploy-guide")
async def download_deploy_guide():
    """下载电视部署上线操作文档"""
    doc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "电视部署上线操作文档.docx")
    if not os.path.exists(doc_path):
        raise HTTPException(status_code=404, detail="部署文档尚未生成，请先运行 docs/generate_deploy_doc.py")
    return FileResponse(doc_path, filename="电视部署上线操作文档.docx", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
