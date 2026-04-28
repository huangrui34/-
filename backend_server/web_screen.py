"""
网页版远程屏幕查看器 - 30FPS H.264 视频流
运行方式: python web_screen.py
访问: http://localhost:8002
不影响现有项目，测试完可删除
"""

import asyncio
import base64
import io
import subprocess
import os
import sys
import time
import tempfile
import threading
import queue

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Web Screen Viewer 30FPS")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def resolve_adb():
    env = os.environ.get("ADB_PATH")
    if env and os.path.exists(env):
        return env
    base = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base, "scrcpy", "adb.exe"),
    ]
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if sdk:
        candidates.append(os.path.join(sdk, "platform-tools", "adb.exe"))
    candidates.append(os.path.join(os.path.expanduser("~"), "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"))
    for c in candidates:
        if os.path.exists(c):
            return c
    return "adb"


def resolve_scrcpy():
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "scrcpy", "scrcpy.exe")
    if os.path.exists(path):
        return path
    return "scrcpy"


ADB = resolve_adb()
SCRCPY = resolve_scrcpy()


def adb_connect(ip: str) -> bool:
    try:
        r = subprocess.run([ADB, "connect", f"{ip}:5555"], capture_output=True, text=True, timeout=5)
        return "connected" in r.stdout.lower() or "already connected" in r.stdout.lower()
    except Exception:
        return False


def adb_key(device_addr: str, keycode: str):
    try:
        subprocess.run([ADB, "-s", device_addr, "shell", "input", "keyevent", keycode], timeout=5)
    except Exception:
        pass


def adb_tap(device_addr: str, x: int, y: int):
    try:
        subprocess.run([ADB, "-s", device_addr, "shell", "input", "tap", str(x), str(y)], timeout=5)
    except Exception:
        pass


def adb_swipe(device_addr: str, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
    try:
        subprocess.run([ADB, "-s", device_addr, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)], timeout=5)
    except Exception:
        pass


def adb_shell_cmd(device_addr: str, cmd: str) -> str:
    try:
        parts = cmd.split()
        result = subprocess.run([ADB, "-s", device_addr] + parts, capture_output=True, text=True, timeout=30)
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "Command timed out (30s)"
    except Exception as e:
        return str(e)


# ============ H.264 视频流模式 (scrcpy + PyAV) ============

class ScrcpyStream:
    """使用 scrcpy 录制 MKV + PyAV 实时解码，实现 30 FPS 视频流"""

    def __init__(self, device_addr: str, max_fps: int = 30, quality: int = 50, max_width: int = 960):
        self.device_addr = device_addr
        self.max_fps = max_fps
        self.quality = quality
        self.max_width = max_width
        self.process = None
        self.mkv_path = None
        self.running = False
        self._thread = None
        # 线程安全队列（decode线程 -> asyncio主线程）
        self._frame_queue = queue.Queue(maxsize=30)
        self._actual_fps = 0
        self._frame_count = 0
        self._fps_start = time.time()
        self._start_error = None

    def start(self):
        """启动 scrcpy 录制（非阻塞，在后台线程中等待启动）"""
        self.running = True
        self._start_error = None

        # 创建临时 MKV 文件
        tmp_dir = tempfile.gettempdir()
        self.mkv_path = os.path.join(tmp_dir, f"scrcpy_stream_{self.device_addr.replace(':', '_')}.mkv")
        if os.path.exists(self.mkv_path):
            try:
                os.remove(self.mkv_path)
            except Exception:
                pass

        # 启动 scrcpy 录制
        cmd = [
            SCRCPY,
            "--serial", self.device_addr,
            "-N",
            "--no-audio",
            "--max-size", str(self.max_width),
            "--max-fps", str(self.max_fps),
            "--video-bit-rate", "2M",
            "--record", self.mkv_path,
            "--record-format", "mkv",
        ]
        print(f"[STREAM] Starting scrcpy: {' '.join(cmd)}")
        try:
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            self._start_error = str(e)
            self.running = False
            return

        # 在后台线程中等待文件创建并启动解码
        self._thread = threading.Thread(target=self._startup_and_decode, daemon=True)
        self._thread.start()

    def _startup_and_decode(self):
        """后台线程：等待MKV文件 + 解码循环"""
        # 等待 MKV 文件创建
        for _ in range(40):  # 20秒超时
            if not self.running:
                return
            if self.process.poll() is not None:
                stderr_output = ""
                try:
                    stderr_output = self.process.stderr.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                self._start_error = f"scrcpy exited: {stderr_output[:200]}"
                print(f"[STREAM] scrcpy exited early: {stderr_output[:200]}")
                self.running = False
                return
            if os.path.exists(self.mkv_path) and os.path.getsize(self.mkv_path) > 4096:
                break
            time.sleep(0.5)
        else:
            self._start_error = "MKV file not created within 20s"
            print("[STREAM] MKV file not created in time")
            self.running = False
            return

        print(f"[STREAM] MKV file ready ({os.path.getsize(self.mkv_path)} bytes), starting decode")
        self._decode_loop()

    def stop(self):
        """停止录制和解码"""
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        if self._thread:
            self._thread.join(timeout=5)
        # 清理 MKV 文件
        if self.mkv_path and os.path.exists(self.mkv_path):
            try:
                os.remove(self.mkv_path)
            except Exception:
                pass
        print("[STREAM] Stopped")

    def get_frame(self, timeout: float = 0.1) -> bytes | None:
        """从线程安全队列获取一帧（供asyncio调用）"""
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _decode_loop(self):
        """在线程中持续解码 MKV 文件中的视频帧"""
        import av
        from PIL import Image

        retry_count = 0
        max_retries = 10

        while self.running:
            try:
                # 检查文件是否在增长
                try:
                    current_size = os.path.getsize(self.mkv_path)
                except OSError:
                    time.sleep(0.5)
                    continue

                if current_size < 4096:
                    time.sleep(0.3)
                    continue

                # 打开 MKV 并解码
                try:
                    container = av.open(self.mkv_path)
                except Exception as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        print(f"[STREAM] Cannot open MKV after {max_retries} retries: {e}")
                        break
                    time.sleep(0.5)
                    continue

                retry_count = 0
                stream = container.streams.video[0]
                frame_idx = 0

                for frame in container.decode(stream):
                    if not self.running:
                        break

                    frame_idx += 1

                    # 跳帧: scrcpy录制30fps，如果用户要求更低帧率则跳帧
                    if self.max_fps < 30 and frame_idx % max(1, int(30 / self.max_fps)) != 0:
                        continue

                    try:
                        img = frame.to_image()
                        if img.mode == "RGBA":
                            img = img.convert("RGB")

                        w, h = img.size
                        if w > self.max_width:
                            new_h = int(h * self.max_width / w)
                            img = img.resize((self.max_width, new_h), Image.LANCZOS)

                        buf = io.BytesIO()
                        img.save(buf, format="JPEG", quality=self.quality)
                        jpeg_data = buf.getvalue()

                        # 放入线程安全队列
                        try:
                            self._frame_queue.put_nowait(jpeg_data)
                        except queue.Full:
                            # 队列满则丢弃最旧的帧
                            try:
                                self._frame_queue.get_nowait()
                            except queue.Empty:
                                pass
                            try:
                                self._frame_queue.put_nowait(jpeg_data)
                            except queue.Full:
                                pass

                        # 统计 FPS
                        self._frame_count += 1
                        elapsed = time.time() - self._fps_start
                        if elapsed >= 2.0:
                            self._actual_fps = self._frame_count / elapsed
                            self._frame_count = 0
                            self._fps_start = time.time()

                    except Exception:
                        pass

                container.close()

                # 解码到文件末尾后等一小会再重新打开
                time.sleep(0.05)

            except Exception as e:
                if self.running:
                    print(f"[STREAM] Decode error: {e}")
                    time.sleep(0.5)

    @property
    def actual_fps(self):
        return round(self._actual_fps, 1)


# ============ Screencap 回退模式 (低帧率) ============

def adb_screencap(device_addr: str) -> bytes | None:
    import tempfile as tf
    try:
        result = subprocess.run(
            [ADB, "-s", device_addr, "exec-out", "screencap", "-p"],
            capture_output=True, timeout=8
        )
        png_data = result.stdout if result.returncode == 0 and len(result.stdout) > 1000 else None

        if not png_data:
            tmp_remote = "/sdcard/web_screen_tmp.png"
            tmp_local = os.path.join(tf.gettempdir(), "web_screen_tmp.png")
            subprocess.run([ADB, "-s", device_addr, "shell", "screencap", "-p", tmp_remote], timeout=8, capture_output=True)
            r = subprocess.run([ADB, "-s", device_addr, "pull", tmp_remote, tmp_local], capture_output=True, timeout=8)
            if r.returncode == 0 and os.path.exists(tmp_local) and os.path.getsize(tmp_local) > 1000:
                with open(tmp_local, "rb") as f:
                    png_data = f.read()
                os.remove(tmp_local)
            subprocess.run([ADB, "-s", device_addr, "shell", "rm", tmp_remote], timeout=5, capture_output=True)

        if not png_data:
            return None

        from PIL import Image
        img = Image.open(io.BytesIO(png_data))
        if img.mode == "RGBA":
            img = img.convert("RGB")
        w, h = img.size
        if w > 960:
            new_h = int(h * 960 / w)
            img = img.resize((960, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=55)
        return buf.getvalue()
    except Exception:
        return None


async def screencap_stream_loop(ws: WebSocket, device_addr: str, fps: float = 2.0):
    """低帧率截图回退模式"""
    interval = 1.0 / fps
    loop = asyncio.get_event_loop()
    while True:
        try:
            jpeg_data = await loop.run_in_executor(None, adb_screencap, device_addr)
            if jpeg_data:
                b64 = base64.b64encode(jpeg_data).decode("ascii")
                await ws.send_json({"type": "frame", "data": b64})
            else:
                await ws.send_json({"type": "error", "msg": "截图失败"})
            await asyncio.sleep(interval)
        except WebSocketDisconnect:
            break
        except Exception as e:
            try:
                await ws.send_json({"type": "error", "msg": str(e)})
            except Exception:
                break
            await asyncio.sleep(1)


# ============ WebSocket 端点 ============

@app.websocket("/ws/screen/{ip}")
async def ws_screen(ws: WebSocket, ip: str):
    try:
        ws._websocket.max_size = 4 * 1024 * 1024
    except Exception:
        pass
    await ws.accept()
    device_addr = f"{ip}:5555"

    # 连接 ADB
    connected = await asyncio.get_event_loop().run_in_executor(None, adb_connect, ip)
    if not connected:
        await ws.send_json({"type": "error", "msg": f"ADB连接失败: {ip}:5555"})
        await ws.close()
        return

    await ws.send_json({"type": "status", "msg": f"ADB已连接，正在启动视频流..."})

    stream = None
    screencap_task = None
    forward_task = None

    # 尝试 H.264 视频流模式
    try:
        stream = ScrcpyStream(device_addr, max_fps=30, quality=50, max_width=960)
        # start() 是非阻塞的，在后台线程启动
        stream.start()

        # 等待首帧或超时（最多20秒）
        first_frame = None
        for i in range(40):
            await asyncio.sleep(0.5)
            # 检查启动错误
            if stream._start_error:
                print(f"[STREAM] Start error: {stream._start_error}")
                break
            if stream.process and stream.process.poll() is not None:
                print("[STREAM] scrcpy exited early, falling back to screencap")
                break
            # 尝试获取帧
            frame = stream.get_frame(timeout=0.01)
            if frame:
                first_frame = frame
                break

        if first_frame:
            # H.264 流模式成功
            await ws.send_json({"type": "status", "msg": f"视频流已启动 ({ip}) - 30 FPS"})
            await ws.send_json({"type": "mode", "mode": "h264", "fps": 30})

            # 发送首帧
            b64 = base64.b64encode(first_frame).decode("ascii")
            await ws.send_json({"type": "frame", "data": b64})

            # 启动帧转发任务
            async def forward_frames():
                while stream and stream.running:
                    try:
                        # 从线程安全队列获取帧
                        jpeg_data = await asyncio.get_event_loop().run_in_executor(
                            None, stream.get_frame, 0.5
                        )
                        if jpeg_data:
                            b64 = base64.b64encode(jpeg_data).decode("ascii")
                            await ws.send_json({"type": "frame", "data": b64})
                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        if "Cannot call" in str(e) or "close" in str(e).lower():
                            break
                        await asyncio.sleep(0.1)

            forward_task = asyncio.create_task(forward_frames())
        else:
            # 回退到截图模式
            if stream:
                stream.stop()
                stream = None
            await ws.send_json({"type": "status", "msg": f"H.264流不可用，使用截图模式 ({ip})"})
            await ws.send_json({"type": "mode", "mode": "screencap", "fps": 2})
            screencap_task = asyncio.create_task(screencap_stream_loop(ws, device_addr, fps=2.0))

    except Exception as e:
        print(f"[STREAM] H.264 failed: {e}, falling back to screencap")
        if stream:
            stream.stop()
            stream = None
        try:
            await ws.send_json({"type": "status", "msg": f"使用截图模式 ({ip})"})
            await ws.send_json({"type": "mode", "mode": "screencap", "fps": 2})
            screencap_task = asyncio.create_task(screencap_stream_loop(ws, device_addr, fps=2.0))
        except Exception:
            pass

    # 接收控制命令
    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action")
            loop = asyncio.get_event_loop()

            if action == "tap":
                await loop.run_in_executor(None, adb_tap, device_addr, data.get("x", 0), data.get("y", 0))
            elif action == "key":
                await loop.run_in_executor(None, adb_key, device_addr, data.get("key", ""))
            elif action == "swipe":
                await loop.run_in_executor(None, adb_swipe, device_addr,
                    data.get("x1", 0), data.get("y1", 0), data.get("x2", 0), data.get("y2", 0), data.get("duration", 300))
            elif action == "shell":
                output = await loop.run_in_executor(None, adb_shell_cmd, device_addr, data.get("cmd", ""))
                await ws.send_json({"type": "shell_output", "output": output})
            elif action == "set_fps":
                fps = int(float(data.get("fps", 30)))
                fps = max(1, min(fps, 60))
                if stream:
                    stream.max_fps = fps
                    await ws.send_json({"type": "status", "msg": f"帧率已设为 {fps} FPS"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if stream:
            stream.stop()
        if forward_task:
            forward_task.cancel()
        if screencap_task:
            screencap_task.cancel()


@app.get("/")
async def index():
    return HTMLResponse(HTML_PAGE)


HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Web Screen Viewer - 30FPS</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; display: flex; flex-direction: column; height: 100vh; }
.header { padding: 10px 20px; background: #16213e; display: flex; gap: 12px; align-items: center; border-bottom: 1px solid #0f3460; }
.header h1 { font-size: 1.1rem; color: #e94560; white-space: nowrap; }
.header input { padding: 8px 12px; border: 1px solid #0f3460; border-radius: 6px; background: #1a1a2e; color: #eee; font-size: 0.9rem; width: 180px; }
.header button { padding: 8px 18px; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; transition: opacity 0.2s; }
.header button:hover { opacity: 0.85; }
.btn-connect { background: #e94560; color: white; }
.btn-disconnect { background: #6c757d; color: white; }
.mode-badge { font-size: 0.75rem; padding: 3px 8px; border-radius: 4px; font-weight: 600; }
.mode-h264 { background: #28a745; color: white; }
.mode-screencap { background: #ffc107; color: #333; }
.main { display: flex; flex: 1; overflow: hidden; }
.screen-area { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 12px; position: relative; background: #0f0f23; min-width: 0; }
.screen-area img { max-width: 100%; max-height: calc(100vh - 120px); border-radius: 8px; box-shadow: 0 0 30px rgba(233,69,96,0.2); cursor: crosshair; image-rendering: auto; }
.placeholder { text-align: center; color: #6c757d; }
.placeholder .icon { font-size: 4rem; margin-bottom: 12px; }
.status-bar { padding: 5px 20px; background: #16213e; font-size: 0.8rem; color: #6c757d; display: flex; justify-content: space-between; border-top: 1px solid #0f3460; }
.controls-panel { width: 240px; background: #16213e; border-left: 1px solid #0f3460; padding: 12px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.panel-section { background: #1a1a2e; border-radius: 8px; padding: 10px; }
.panel-section h3 { font-size: 0.82rem; color: #e94560; margin-bottom: 8px; }
.key-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; }
.key-grid button { padding: 8px 4px; border: 1px solid #0f3460; border-radius: 6px; background: #16213e; color: #eee; cursor: pointer; font-size: 0.82rem; transition: all 0.15s; }
.key-grid button:hover { background: #e94560; border-color: #e94560; }
.key-grid button:active { transform: scale(0.95); }
.fps-control { display: flex; align-items: center; gap: 6px; font-size: 0.78rem; }
.fps-control input[type="range"] { flex: 1; }
.shell-input { display: flex; gap: 5px; }
.shell-input input { flex: 1; padding: 5px 8px; border: 1px solid #0f3460; border-radius: 4px; background: #0f0f23; color: #eee; font-family: Consolas, monospace; font-size: 0.78rem; }
.shell-input button { padding: 5px 10px; border: none; border-radius: 4px; background: #0f3460; color: #eee; cursor: pointer; font-size: 0.78rem; }
.shell-output { background: #0f0f23; border-radius: 4px; padding: 6px; font-family: Consolas, monospace; font-size: 0.72rem; color: #8f8; max-height: 100px; overflow-y: auto; margin-top: 5px; white-space: pre-wrap; word-break: break-all; }
.quick-btn { padding: 3px 7px; border: 1px solid #0f3460; border-radius: 4px; background: #16213e; color: #eee; cursor: pointer; font-size: 0.7rem; }
.quick-btn:hover { background: #0f3460; }
</style>
</head>
<body>

<div class="header">
    <h1>Web Screen Viewer</h1>
    <input type="text" id="ipInput" placeholder="电视IP (如 10.181.184.226)" value="">
    <button class="btn-connect" id="connectBtn" onclick="doConnect()">连接</button>
    <button class="btn-disconnect" id="disconnectBtn" onclick="doDisconnect()" style="display:none;">断开</button>
    <span id="modeBadge" class="mode-badge" style="display:none;"></span>
    <span id="statusText" style="font-size:0.82rem; color:#6c757d;">未连接</span>
</div>

<div class="main">
    <div class="screen-area">
        <div class="placeholder" id="placeholder">
            <div class="icon">📺</div>
            <div>输入电视IP，点击连接开始远程查看</div>
            <div style="margin-top:8px; font-size:0.8rem; color:#555;">支持30FPS视频流（需要scrcpy）</div>
        </div>
        <img id="screenImg" style="display:none;" onmousedown="onMouseDown(event)" onmousemove="onMouseMove(event)" onmouseup="onMouseUp(event)">
    </div>

    <div class="controls-panel">
        <div class="panel-section">
            <h3>🎮 方向控制</h3>
            <div class="key-grid">
                <div></div>
                <button onclick="sendKey('19')">▲</button>
                <div></div>
                <button onclick="sendKey('21')">◀</button>
                <button onclick="sendKey('66')">OK</button>
                <button onclick="sendKey('22')">▶</button>
                <div></div>
                <button onclick="sendKey('20')">▼</button>
                <div></div>
            </div>
        </div>

        <div class="panel-section">
            <h3>🔧 功能键</h3>
            <div class="key-grid">
                <button onclick="sendKey('4')">返回</button>
                <button onclick="sendKey('3')">主页</button>
                <button onclick="sendKey('82')">菜单</button>
                <button onclick="sendKey('24')">音量+</button>
                <button onclick="sendKey('25')">音量-</button>
                <button onclick="sendKey('26')">电源</button>
            </div>
        </div>

        <div class="panel-section">
            <h3>⚡ 帧率</h3>
            <div class="fps-control">
                <span>1</span>
                <input type="range" id="fpsSlider" min="1" max="60" step="1" value="30" oninput="changeFps(this.value)">
                <span>60</span>
                <span id="fpsLabel" style="color:#e94560; font-weight:600;">30 FPS</span>
            </div>
        </div>

        <div class="panel-section">
            <h3>💻 快捷命令</h3>
            <div style="display:flex; flex-wrap:wrap; gap:3px;">
                <button class="quick-btn" onclick="sendShell('shell dumpsys battery')">电池</button>
                <button class="quick-btn" onclick="sendShell('shell getprop ro.product.model')">型号</button>
                <button class="quick-btn" onclick="sendShell('shell pm list packages -3')">应用</button>
                <button class="quick-btn" onclick="sendShell('shell input keyevent 3')">HOME</button>
                <button class="quick-btn" onclick="sendShell('shell input keyevent 4')">返回</button>
            </div>
            <div class="shell-input" style="margin-top:6px;">
                <input type="text" id="shellInput" placeholder="shell命令" onkeydown="if(event.key==='Enter')sendShellCmd()">
                <button onclick="sendShellCmd()">执行</button>
            </div>
            <div class="shell-output" id="shellOutput"></div>
        </div>
    </div>
</div>

<div class="status-bar">
    <span id="leftStatus">就绪</span>
    <span id="rightStatus">点击屏幕可控制电视</span>
</div>

<script>
let ws = null;
let frameCount = 0;
let fpsTimer = null;
let currentFps = 0;
let isDragging = false;
let dragStartX = 0, dragStartY = 0;
let currentMode = '';

function doConnect() {
    const ip = document.getElementById('ipInput').value.trim();
    if (!ip) return alert('请输入IP');

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${location.host}/ws/screen/${ip}`);

    document.getElementById('statusText').textContent = '连接中...';
    document.getElementById('statusText').style.color = '#f9ab00';

    ws.onopen = () => {
        document.getElementById('connectBtn').style.display = 'none';
        document.getElementById('disconnectBtn').style.display = 'inline-block';
        document.getElementById('placeholder').style.display = 'none';
        document.getElementById('screenImg').style.display = 'block';
        startFpsCounter();
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'frame') {
            document.getElementById('screenImg').src = 'data:image/jpeg;base64,' + data.data;
            frameCount++;
        } else if (data.type === 'status') {
            document.getElementById('leftStatus').textContent = data.msg;
        } else if (data.type === 'mode') {
            currentMode = data.mode;
            const badge = document.getElementById('modeBadge');
            badge.style.display = 'inline-block';
            if (data.mode === 'h264') {
                badge.className = 'mode-badge mode-h264';
                badge.textContent = 'H.264 ' + data.fps + 'FPS';
            } else {
                badge.className = 'mode-badge mode-screencap';
                badge.textContent = '截图 ' + data.fps + 'FPS';
            }
        } else if (data.type === 'fps') {
            // 服务器报告的实际FPS
        } else if (data.type === 'error') {
            document.getElementById('leftStatus').textContent = '错误: ' + data.msg;
        } else if (data.type === 'shell_output') {
            document.getElementById('shellOutput').textContent = data.output;
        }
    };

    ws.onclose = () => {
        document.getElementById('connectBtn').style.display = 'inline-block';
        document.getElementById('disconnectBtn').style.display = 'none';
        document.getElementById('modeBadge').style.display = 'none';
        document.getElementById('statusText').textContent = '已断开';
        document.getElementById('statusText').style.color = '#6c757d';
        stopFpsCounter();
    };

    ws.onerror = () => {
        document.getElementById('statusText').textContent = '连接失败';
        document.getElementById('statusText').style.color = '#dc3545';
    };
}

function doDisconnect() {
    if (ws) { ws.close(); ws = null; }
    document.getElementById('screenImg').style.display = 'none';
    document.getElementById('placeholder').style.display = 'block';
}

function sendKey(keycode) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({action: 'key', key: keycode}));
    }
}

function sendShell(cmd) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({action: 'shell', cmd: cmd}));
    }
}

function sendShellCmd() {
    const cmd = document.getElementById('shellInput').value.trim();
    if (cmd) sendShell(cmd);
}

function changeFps(val) {
    document.getElementById('fpsLabel').textContent = val + ' FPS';
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({action: 'set_fps', fps: parseInt(val)}));
    }
}

function screenCoords(event) {
    const img = event.target;
    const rect = img.getBoundingClientRect();
    const x = Math.round((event.clientX - rect.left) / rect.width * 1920);
    const y = Math.round((event.clientY - rect.top) / rect.height * 1080);
    return {x, y};
}

function onMouseDown(event) {
    isDragging = false;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    const {x, y} = screenCoords(event);
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({action: 'tap', x, y}));
    }
}

function onMouseMove(event) {
    if (event.buttons !== 1) return;
    const dx = event.clientX - dragStartX;
    const dy = event.clientY - dragStartY;
    if (Math.abs(dx) > 10 || Math.abs(dy) > 10) {
        isDragging = true;
    }
}

function onMouseUp(event) {
    if (!isDragging) return;
    const start = screenCoords({clientX: dragStartX, clientY: dragStartY, target: event.target});
    const end = screenCoords(event);
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({action: 'swipe', x1: start.x, y1: start.y, x2: end.x, y2: end.y, duration: 300}));
    }
    isDragging = false;
}

function startFpsCounter() {
    frameCount = 0;
    currentFps = 0;
    fpsTimer = setInterval(() => {
        currentFps = frameCount;
        frameCount = 0;
        document.getElementById('rightStatus').textContent = currentFps + ' FPS | 点击屏幕控制';
    }, 1000);
}

function stopFpsCounter() {
    if (fpsTimer) { clearInterval(fpsTimer); fpsTimer = null; }
    document.getElementById('rightStatus').textContent = '点击屏幕可控制电视';
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  Web Screen Viewer 30FPS 测试服务")
    print("  访问: http://localhost:8002")
    print("  依赖: pip install av pillow")
    print("  Ctrl+C 停止")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8002)
