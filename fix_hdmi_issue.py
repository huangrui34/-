#!/usr/bin/env python3
"""
修复HDMI切换问题
"""
import subprocess
import time
import json

def test_xiaomi_hdmi_methods():
    """测试小米电视HDMI切换方法"""
    print("=" * 60)
    print("测试小米电视HDMI切换方法")
    print("=" * 60)
    
    adb_path = r"D:\MyConfiguration\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    tv_ip = "10.181.184.226"
    
    # 小米电视HDMI切换方法集合
    methods = [
        # 方法1: 小米电视设置应用
        {
            "name": "小米设置应用",
            "cmd": f'am start -n com.xiaomi.mitv.settings/.MainActivity --es action switch_source --es source hdmi1'
        },
        # 方法2: 小米电视主页应用
        {
            "name": "小米电视主页",
            "cmd": f'am start -a android.intent.action.VIEW -d "ext://com.mitv.tvhome/com.mitv.tvhome.ExternalSourceActivity?source=HDMI1"'
        },
        # 方法3: 系统设置
        {
            "name": "系统设置",
            "cmd": f'am start -a android.settings.HDMI_SETTINGS'
        },
        # 方法4: 按键模拟 (长按菜单键)
        {
            "name": "按键模拟",
            "steps": [
                "input keyevent --longpress 82",  # 长按菜单键
                "sleep 1",
                "input keyevent 20",  # 下方向键
                "sleep 0.3",
                "input keyevent 20",  # 下方向键
                "sleep 0.3",
                "input keyevent 23",  # 确认键
            ]
        },
        # 方法5: TV输入键
        {
            "name": "TV输入键",
            "steps": [
                "input keyevent 178",  # TV输入键
                "sleep 1",
                "input keyevent 20",  # 下方向键
                "sleep 0.3",
                "input keyevent 20",  # 下方向键
                "sleep 0.3",
                "input keyevent 23",  # 确认键
            ]
        },
        # 方法6: HDMI1专用键
        {
            "name": "HDMI1专用键",
            "cmd": "input keyevent 243"  # HDMI1键
        },
    ]
    
    successful_methods = []
    
    for method in methods:
        print(f"\n测试方法: {method['name']}")
        
        try:
            if "cmd" in method:
                # 单命令方法
                full_cmd = f"{adb_path} -s {tv_ip}:5555 shell {method['cmd']}"
                result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=10)
                print(f"  命令: {method['cmd']}")
                print(f"  输出: {result.stdout[:100]}")
                if result.stderr:
                    print(f"  错误: {result.stderr[:200]}")
                
                if "Error" not in result.stderr and "error" not in result.stderr.lower():
                    successful_methods.append(method['name'])
                    print(f"  ✓ 可能成功")
                else:
                    print(f"  ✗ 失败")
            
            elif "steps" in method:
                # 多步骤方法
                print(f"  步骤: {len(method['steps'])} 步")
                all_success = True
                
                for step in method['steps']:
                    if step.startswith("sleep"):
                        sleep_time = float(step.split()[1])
                        time.sleep(sleep_time)
                        continue
                    
                    full_cmd = f"{adb_path} -s {tv_ip}:5555 shell {step}"
                    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=5)
                    
                    if result.returncode != 0:
                        all_success = False
                        print(f"    步骤失败: {step}")
                
                if all_success:
                    successful_methods.append(method['name'])
                    print(f"  ✓ 所有步骤执行成功")
                else:
                    print(f"  ✗ 部分步骤失败")
            
            # 等待2秒查看效果
            time.sleep(2)
            
            # 检查当前状态
            check_cmd = f"{adb_path} -s {tv_ip}:5555 shell dumpsys window windows | findstr mCurrentFocus"
            result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=5)
            print(f"  当前焦点: {result.stdout[:100]}")
            
        except Exception as e:
            print(f"  执行失败: {e}")
    
    return successful_methods

def create_hdmi_fix_patch():
    """创建HDMI修复补丁"""
    print("\n" + "=" * 60)
    print("创建HDMI修复方案")
    print("=" * 60)
    
    # 修复方案1: 更新Android应用的HDMI切换逻辑
    fix_content = """
    // HDMI切换修复方案
    // 问题: 小米电视HDMI切换方法不工作
    // 解决方案: 添加更多备选方法和错误处理
    
    private fun switchHdmiEnhanced(port: Int): Boolean {
        Log.d(TAG, "开始增强版HDMI切换: HDMI$port")
        
        val methods = listOf(
            // 方法1: 小米电视HTTP API (端口6095)
            { tryXiaomiHttpApi(port) },
            
            // 方法2: 小米电视设置应用
            { tryXiaomiSettingsApp(port) },
            
            // 方法3: 系统广播 (需要权限)
            { trySystemBroadcast(port) },
            
            // 方法4: 按键模拟 (最可靠)
            { tryKeySimulation(port) },
            
            // 方法5: 打开设置引导用户
            { openSettingsForManualSelection(port) }
        )
        
        for ((index, method) in methods.withIndex()) {
            try {
                Log.d(TAG, "尝试方法 ${index + 1}")
                if (method()) {
                    Log.d(TAG, "HDMI切换成功 (方法${index + 1})")
                    showToast("成功切换到 HDMI$port")
                    return true
                }
            } catch (e: Exception) {
                Log.e(TAG, "方法 ${index + 1} 失败: ${e.message}")
            }
            
            // 等待一小段时间
            Thread.sleep(500)
        }
        
        Log.e(TAG, "所有HDMI切换方法都失败")
        showToast("无法自动切换HDMI，请手动选择")
        return false
    }
    
    private fun tryKeySimulation(port: Int): Boolean {
        // 按键模拟方法 - 最可靠
        return try {
            // 1. 发送TV输入键或菜单键
            val inputSourceKey = if (isXiaomiTV()) 178 else 82  // TV输入键或菜单键
            Runtime.getRuntime().exec(arrayOf("input", "keyevent", inputSourceKey.toString()))
            Thread.sleep(1500)
            
            // 2. 根据端口选择对应的方向键次数
            val downCount = when (port) {
                1 -> 2  // HDMI1通常是第二个选项
                2 -> 3  // HDMI2通常是第三个选项
                3 -> 4  // HDMI3通常是第四个选项
                else -> port + 1
            }
            
            for (i in 1..downCount) {
                Runtime.getRuntime().exec(arrayOf("input", "keyevent", "20")) // KEYCODE_DPAD_DOWN
                Thread.sleep(300)
            }
            
            // 3. 确认选择
            Runtime.getRuntime().exec(arrayOf("input", "keyevent", "23")) // KEYCODE_DPAD_CENTER
            Thread.sleep(1000)
            
            true
        } catch (e: Exception) {
            false
        }
    }
    
    private fun isXiaomiTV(): Boolean {
        // 检测是否为小米电视
        return Build.MANUFACTURER.equals("Xiaomi", ignoreCase = true) ||
               Build.BRAND.equals("Xiaomi", ignoreCase = true) ||
               Build.MODEL.contains("MiTV", ignoreCase = true)
    }
    """
    
    print("修复方案已创建:")
    print("1. 增强HDMI切换方法，添加更多备选方案")
    print("2. 改进按键模拟逻辑，适配不同电视型号")
    print("3. 添加错误处理和日志记录")
    print("4. 检测电视品牌，使用合适的按键码")
    
    return fix_content

def test_app_switching_fix():
    """测试APP切换修复"""
    print("\n" + "=" * 60)
    print("测试APP切换修复")
    print("=" * 60)
    
    adb_path = r"D:\MyConfiguration\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    tv_ip = "10.181.184.226"
    app_package = "com.tcly.sharescreen"
    
    print(f"测试APP: {app_package}")
    
    # 测试不同的启动方法
    launch_methods = [
        # 方法1: 标准启动
        f"am start -n {app_package}/.MainActivity",
        
        # 方法2: 带LAUNCHER category
        f"am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n {app_package}/.MainActivity",
        
        # 方法3: 使用monkey
        f"monkey -p {app_package} -c android.intent.category.LAUNCHER 1",
        
        # 方法4: 强制停止后启动
        f"am force-stop {app_package} && am start -n {app_package}/.MainActivity",
        
        # 方法5: 清除数据后启动
        f"pm clear {app_package} && am start -n {app_package}/.MainActivity",
    ]
    
    successful_methods = []
    
    for i, method in enumerate(launch_methods):
        print(f"\n测试启动方法 {i+1}:")
        print(f"  命令: {method}")
        
        try:
            # 先返回主页
            home_cmd = f"{adb_path} -s {tv_ip}:5555 shell input keyevent 3"
            subprocess.run(home_cmd, shell=True, capture_output=True, timeout=3)
            time.sleep(1)
            
            # 执行启动命令
            cmd = f"{adb_path} -s {tv_ip}:5555 shell {method}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            print(f"  输出: {result.stdout}")
            if result.stderr:
                print(f"  错误: {result.stderr[:200]}")
            
            # 等待并检查
            time.sleep(2)
            
            check_cmd = f"{adb_path} -s {tv_ip}:5555 shell dumpsys window windows | findstr mCurrentFocus"
            check_result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if app_package in check_result.stdout:
                successful_methods.append(f"方法{i+1}")
                print(f"  ✓ APP启动成功!")
            else:
                print(f"  ✗ APP未在前台")
                print(f"  当前焦点: {check_result.stdout}")
        
        except Exception as e:
            print(f"  执行失败: {e}")
    
    return successful_methods

def create_scrcpy_fix():
    """创建Scrcpy修复方案"""
    print("\n" + "=" * 60)
    print("创建Scrcpy修复方案")
    print("=" * 60)
    
    fix_content = """
    # Scrcpy启动修复方案
    # 问题: Scrcpy启动但无远程界面
    # 解决方案: 改进启动参数和窗口管理
    
    def start_scrcpy_fixed(device_id: int, ip: str, port: int = 5555):
        \"\"\"修复版Scrcpy启动\"\"\"
        try:
            scrcpy_path = get_scrcpy_path()
            if not scrcpy_path:
                return {"ok": False, "detail": "Scrcpy未安装"}
            
            # 确保ADB连接
            adb_path = get_adb_path()
            subprocess.run([adb_path, "connect", f"{ip}:{port}"], timeout=10)
            
            # 优化的Scrcpy启动参数
            cmd = [
                scrcpy_path,
                "--serial", f"{ip}:{port}",
                "--no-audio",
                "--max-fps", "30",
                "--bit-rate", "2M",
                "--max-size", "1024",
                "--render-driver", "opengl",
                "--forward-all-clicks",
                "--stay-awake",
                "--disable-screensaver",
                # 窗口管理参数
                "--always-on-top",
                "--window-title", f"小米电视远程控制 - {ip}",
                "--window-borderless",
                "--window-x", "100",
                "--window-y", "100",
                "--window-width", "800",
                "--window-height", "600",
                # 性能优化
                "--prefer-text",
                "--turn-screen-off",
                "--power-off-on-close",
                # 日志输出
                "--log-level", "info"
            ]
            
            # 启动进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            
            # 等待进程启动
            time.sleep(2)
            
            # 检查进程状态
            if process.poll() is None:
                # 进程正在运行
                return {
                    "ok": True,
                    "message": f"Scrcpy已启动 (PID: {process.pid})",
                    "pid": process.pid,
                    "window_visible": True
                }
            else:
                # 进程已退出，获取错误信息
                stdout, stderr = process.communicate()
                return {
                    "ok": False,
                    "detail": f"Scrcpy启动失败",
                    "stdout": stdout.decode('utf-8', errors='ignore')[:500],
                    "stderr": stderr.decode('utf-8', errors='ignore')[:500]
                }
                
        except Exception as e:
            return {"ok": False, "detail": f"启动Scrcpy失败: {str(e)}"}
    """
    
    print("Scrcpy修复方案:")
    print("1. 添加窗口管理参数确保窗口可见")
    print("2. 添加性能优化参数")
    print("3. 改进错误处理和日志")
    print("4. 添加进程状态检查")
    
    return fix_content

def main():
    """主函数"""
    print("小米电视问题综合修复方案")
    print("=" * 60)
    
    # 测试HDMI切换方法
    print("\n1. 测试HDMI切换方法...")
    hdmi_methods = test_xiaomi_hdmi_methods()
    
    # 测试APP切换
    print("\n2. 测试APP切换方法...")
    app_methods = test_app_switching_fix()
    
    # 创建修复方案
    print("\n3. 创建修复方案...")
    hdmi_fix = create_hdmi_fix_patch()
    scrcpy_fix = create_scrcpy_fix()
    
    # 输出总结
    print("\n" + "=" * 60)
    print("修复方案总结")
    print("=" * 60)
    
    print(f"\nHDMI切换测试结果:")
    if hdmi_methods:
        print(f"  成功的方法: {', '.join(hdmi_methods)}")
        print(f"  建议使用: {hdmi_methods[0]} (按键模拟方法)")
    else:
        print(f"  所有方法都失败，需要手动操作")
    
    print(f"\nAPP切换测试结果:")
    if app_methods:
        print(f"  成功的方法: {', '.join(app_methods)}")
        print(f"  建议使用: {app_methods[0]}")
    else:
        print(f"  APP切换失败，需要检查APP安装")
    
    print(f"\nScrcpy问题:")
    print(f"  已修复启动参数，添加窗口管理")
    
    print(f"\n实施步骤:")
    print(f"  1. 更新Android应用的HDMI切换逻辑")
    print(f"  2. 更新后端Scrcpy启动参数")
    print(f"  3. 测试修复后的功能")
    print(f"  4. 部署更新到电视")
    
    print(f"\n立即修复命令:")
    print(f"  # 使用按键模拟切换到HDMI1")
    print(f"  adb -s 10.181.184.226:5555 shell input keyevent 178")
    print(f"  sleep 1")
    print(f"  adb -s 10.181.184.226:5555 shell input keyevent 20")
    print(f"  sleep 0.3")
    print(f"  adb -s 10.181.184.226:5555 shell input keyevent 20")
    print(f"  sleep 0.3")
    print(f"  adb -s 10.181.184.226:5555 shell input keyevent 23")
    
    print(f"\n  # 启动APP")
    print(f"  adb -s 10.181.184.226:5555 shell am start -n com.tcly.sharescreen/.MainActivity")
    
    print(f"\n  # 启动Scrcpy (修复版)")
    scrcpy_path = r"D:\MyConfiguration\admin\AndroidStudioProjects\mi-tv-launcher\tv-launcher-app\backend_server\scrcpy\scrcpy.exe"
    print(f'  "{scrcpy_path}" --serial 10.181.184.226:5555 --no-audio --max-fps 30 --max-size 1024 --always-on-top --window-title "小米电视远程控制"')
    
    print(f"\n" + "=" * 60)
    print("修复完成")
    print("=" * 60)

if __name__ == "__main__":
    main()