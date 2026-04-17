package com.company.tvlauncher

import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.app.ActivityManager

class LauncherExecutor(private val context: Context) {

    companion object {
        private const val TAG = "LauncherExecutor"
        const val HDMI_TV_PLAYER_PACKAGE = "com.xiaomi.mitv.tvplayer"
    }

    fun execute(policy: LaunchPolicy) {
        if (policy.mode == "app") {
            launchApp(policy.targetAppPackage)
        } else {
            // HDMI模式：先确保小米电视播放器在运行，再执行HDMI切换
            ensureXiaomiTVPlayerRunning(policy.targetHdmiPort)
        }
    }

    /**
     * 清理后台应用，保留指定的包名列表
     * 系统应用和小米电视播放器会被自动保留
     */
    fun cleanupBackgroundApps(keepPackages: List<String>) {
        try {
            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val tasks = am.runningAppProcesses
            if (tasks != null) {
                for (task in tasks) {
                    val processName = task.processName

                    // 检查是否需要保留此进程
                    val shouldKeep = keepPackages.any { keepPackage ->
                        processName.contains(keepPackage)
                    }

                    // 保留条件：
                    // 1. 本应用进程
                    // 2. 系统应用进程 (com.android.*, android.*)
                    // 3. 小米电视播放器 (com.xiaomi.mitv.tvplayer) - HDMI模式必需
                    // 4. 用户指定的保留包名
                    val isSystemProcess = processName.startsWith("com.android.") ||
                                          processName.startsWith("android.") ||
                                          processName.startsWith("com.xiaomi.mitv.systemui") ||
                                          processName.startsWith("com.xiaomi.mitv.settings")

                    val isTvLauncher = processName == context.packageName

                    val isTvPlayer = processName.contains("com.xiaomi.mitv.tvplayer")

                    if (!isSystemProcess && !isTvLauncher && !isTvPlayer && !shouldKeep) {
                        android.util.Log.d(TAG, "清理后台应用: $processName")
                        am.killBackgroundProcesses(processName)
                    }
                }
            }
        } catch (e: Exception) {
            android.util.Log.e(TAG, "清理后台应用失败: ${e.message}")
            e.printStackTrace()
        }
    }

    /**
     * 执行新策略前的完整准备流程
     * 1. 清理所有非必要后台应用
     * 2. 确保HDMI播放器就绪（如果需要）
     */
    fun prepareForNewPolicy(policy: LaunchPolicy) {
        val keepPackages = mutableListOf<String>()

        when (policy.mode) {
            "app" -> {
                // APP模式：保留目标APP
                keepPackages.add(policy.targetAppPackage)
            }
            "hdmi" -> {
                // HDMI模式：保留小米电视播放器APP
                keepPackages.add(HDMI_TV_PLAYER_PACKAGE)
            }
        }

        // 清理后台应用
        cleanupBackgroundApps(keepPackages)
    }

    /**
     * 启动指定包名的APP - 公开方法
     */
    fun launchApp(packageName: String) {
        // 尝试多种启动方法
        val methods = listOf(
            { launchMethod1(packageName) },  // 标准启动方法
            { launchMethod2(packageName) },  // 使用monkey命令
            { launchMethod3(packageName) },  // 使用am命令
            { launchMethod4(packageName) }   // 尝试常见投屏APP包名
        )

        for ((index, method) in methods.withIndex()) {
            try {
                if (method()) {
                    android.util.Log.d(TAG, "成功启动APP: $packageName (方法${index + 1})")
                    return
                }
            } catch (e: Exception) {
                // 继续尝试下一个方法
            }
        }

        android.util.Log.w(TAG, "无法启动目标APP: $packageName")
    }

    /**
     * 强制停止并重新启动APP（用于投屏类APP刷新投屏码）
     */
    fun forceStopAndRestart(packageName: String) {
        android.util.Log.d(TAG, "强制停止并重启APP: $packageName")

        try {
            // 1. 先强制停止APP
            Runtime.getRuntime().exec(arrayOf("am", "force-stop", packageName)).waitFor()
            android.util.Log.d(TAG, "已停止APP: $packageName")

            // 2. 等待短暂时间确保进程完全停止
            Thread.sleep(500)

            // 3. 重新启动APP
            launchApp(packageName)
            android.util.Log.d(TAG, "已重新启动APP: $packageName")
        } catch (e: Exception) {
            android.util.Log.e(TAG, "强制重启APP失败: ${e.message}")
            // 如果强制重启失败，尝试普通启动
            launchApp(packageName)
        }
    }

    /**
     * 检测指定APP是否在运行
     */
    fun isAppRunning(packageName: String): Boolean {
        try {
            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            // 方法1：检查运行中的进程
            val processes = am.runningAppProcesses
            if (processes != null) {
                for (process in processes) {
                    if (process.processName == packageName || process.processName.contains(packageName)) {
                        android.util.Log.d(TAG, "找到运行中的进程: ${process.processName}")
                        return true
                    }
                }
            }

            // 方法2：通过shell命令检查（更可靠）
            try {
                val process = Runtime.getRuntime().exec(arrayOf("sh", "-c", "ps -A | grep $packageName"))
                val reader = java.io.BufferedReader(java.io.InputStreamReader(process.inputStream))
                val output = reader.readLine()
                reader.close()
                process.waitFor()
                if (!output.isNullOrEmpty()) {
                    android.util.Log.d(TAG, "通过ps找到进程: $output")
                    return true
                }
            } catch (e: Exception) {
                // 忽略
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return false
    }

    /**
     * 确保小米电视播放器在运行，用于HDMI模式
     */
    fun ensureTvPlayerRunning(): Boolean {
        return try {
            if (!isAppRunning(HDMI_TV_PLAYER_PACKAGE)) {
                launchApp(HDMI_TV_PLAYER_PACKAGE)
                Thread.sleep(2000)  // 等待启动
            }
            isAppRunning(HDMI_TV_PLAYER_PACKAGE)
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }

    private fun launchMethod1(packageName: String): Boolean {
        // 标准启动方法
        val launchIntent = context.packageManager.getLaunchIntentForPackage(packageName)
        if (launchIntent != null) {
            launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(launchIntent)
            return true
        }
        return false
    }
    
    private fun launchMethod2(packageName: String): Boolean {
        // 使用monkey命令启动
        try {
            val process = Runtime.getRuntime().exec(arrayOf("monkey", "-p", packageName, "-c", "android.intent.category.LAUNCHER", "1"))
            val exitCode = process.waitFor()
            return exitCode == 0
        } catch (e: Exception) {
            return false
        }
    }
    
    private fun launchMethod3(packageName: String): Boolean {
        // 使用am命令启动
        try {
            val process = Runtime.getRuntime().exec(arrayOf("am", "start", "-n", "$packageName/.MainActivity"))
            val exitCode = process.waitFor()
            return exitCode == 0
        } catch (e: Exception) {
            // 尝试其他常见Activity名称
            val activities = listOf(
                ".MainActivity",
                ".SplashActivity",
                ".HomeActivity",
                ".LauncherActivity",
                ".TVMainActivity",
                ".TVHomeActivity"
            )
            
            for (activity in activities) {
                try {
                    val process = Runtime.getRuntime().exec(arrayOf("am", "start", "-n", "$packageName/$activity"))
                    val exitCode = process.waitFor()
                    if (exitCode == 0) {
                        return true
                    }
                } catch (e: Exception) {
                    // 继续尝试下一个Activity
                }
            }
            return false
        }
    }
    
    private fun launchMethod4(packageName: String): Boolean {
        // 尝试常见投屏APP包名
        val commonCastApps = mapOf(
            "com.example.cast" to listOf("com.xiaomi.mitv.cast", "com.xiaomi.mitv.screenmirror", 
                                         "com.xiaomi.mitv.wifidisplay", "com.android.screenmirroring",
                                         "com.xiaomi.mitv.tvcast", "com.xiaomi.mitv.miracast")
        )
        
        // 如果包名是通用名称，尝试常见的小米投屏APP
        if (packageName == "com.example.cast") {
            for (castPackage in commonCastApps["com.example.cast"] ?: emptyList()) {
                try {
                    val launchIntent = context.packageManager.getLaunchIntentForPackage(castPackage)
                    if (launchIntent != null) {
                        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        context.startActivity(launchIntent)
                        return true
                    }
                } catch (e: Exception) {
                    // 继续尝试下一个包名
                }
            }
        }
        
        return false
    }

    private fun ensureXiaomiTVPlayerRunning(hdmiPort: Int) {
        // 小米电视HDMI切换必须先启动小米电视播放器
        val tvPlayerPackage = "com.xiaomi.mitv.tvplayer"

        try {
            // 首先检查播放器是否已经在运行
            if (!isAppRunning(tvPlayerPackage)) {
                // 播放器未运行，先启动它
                android.util.Log.d(TAG, "HDMI模式：启动小米电视播放器")
                val launchIntent = context.packageManager.getLaunchIntentForPackage(tvPlayerPackage)
                if (launchIntent != null) {
                    launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    context.startActivity(launchIntent)

                    // 等待播放器启动（3秒）
                    try {
                        Thread.sleep(3000)
                    } catch (e: InterruptedException) {
                        // 线程中断，继续执行
                    }

                    // 检查播放器是否成功启动
                    if (isAppRunning(tvPlayerPackage)) {
                        android.util.Log.d(TAG, "小米电视播放器启动成功，执行HDMI${hdmiPort}切换")
                    } else {
                        android.util.Log.w(TAG, "小米电视播放器启动失败，尝试直接切换HDMI")
                    }
                } else {
                    // 找不到播放器APK
                    android.util.Log.w(TAG, "未找到小米电视播放器APK: $tvPlayerPackage")
                }
            } else {
                android.util.Log.d(TAG, "小米电视播放器已在运行，直接切换HDMI${hdmiPort}")
            }

            // 执行HDMI切换
            switchHdmi(hdmiPort)
        } catch (e: Exception) {
            android.util.Log.e(TAG, "HDMI切换失败: ${e.message}")
            e.printStackTrace()
            // 发生异常时直接尝试HDMI切换
            switchHdmi(hdmiPort)
        }
    }

    private fun switchHdmi(port: Int) {
        android.util.Log.d(TAG, "开始HDMI${port}切换流程")

        // 获取正确的HDMI输入服务ID
        val hdmiInputService = when (port) {
            1 -> "com.droidlogic.tvinput/.services.Hdmi1InputService"
            2 -> "com.droidlogic.tvinput/.services.Hdmi2InputService"
            3 -> "com.droidlogic.tvinput/.services.Hdmi3InputService"
            else -> "com.droidlogic.tvinput/.services.Hdmi1InputService"
        }
        val hwId = when (port) {
            1 -> "HW5"
            2 -> "HW6"
            3 -> "HW7"
            else -> "HW5"
        }
        val hdmiInputId = "com.droidlogic.tvinput/$hdmiInputService/$hwId"

        // 方法1: 尝试使用TvInputManager API直接切换
        try {
            android.util.Log.d(TAG, "尝试TvInputManager API切换")

            // 先按HOME键
            Runtime.getRuntime().exec(arrayOf("input", "keyevent", "3")).waitFor()
            Thread.sleep(500)

            // 设置系统输入源
            Runtime.getRuntime().exec(arrayOf("settings", "put", "system", "tv_input_id", hdmiInputId)).waitFor()
            android.util.Log.d(TAG, "已设置tv_input_id为: $hdmiInputId")

            // 使用am命令直接调谐到指定HDMI输入
            val tuneCommand = arrayOf(
                "am", "start", "-a", "android.intent.action.VIEW",
                "-d", "content://android.media.tv/passthrough/$hdmiInputId",
                "-n", "com.xiaomi.mitv.tvplayer/.ExternalSourceActivity",
                "--activity-clear-task", "--activity-new-task"
            )
            Runtime.getRuntime().exec(tuneCommand).waitFor()
            android.util.Log.d(TAG, "已发送调谐命令到HDMI$port")

            Thread.sleep(1500)

            // 如果不是HDMI1，需要额外按键导航
            if (port != 1) {
                // 发送TV_INPUT键打开输入源菜单
                Runtime.getRuntime().exec(arrayOf("input", "keyevent", "178")).waitFor()
                Thread.sleep(1200)

                // 根据端口导航
                val downCount = port - 1
                for (i in 1..downCount) {
                    Runtime.getRuntime().exec(arrayOf("input", "keyevent", "20")).waitFor()
                    Thread.sleep(400)
                }

                // 确认选择
                Runtime.getRuntime().exec(arrayOf("input", "keyevent", "23")).waitFor()
                android.util.Log.d(TAG, "已导航并选择HDMI$port")
            }

            android.util.Log.d(TAG, "HDMI${port}切换完成")
            return
        } catch (e: Exception) {
            android.util.Log.e(TAG, "HDMI切换方法1失败: ${e.message}")
        }

        // 方法2: 备用方案 - 打开设置页面让用户手动选择
        try {
            android.util.Log.w(TAG, "尝试备用方案，打开设置页面")
            val intent = Intent(Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
        } catch (e: Exception) {
            android.util.Log.e(TAG, "HDMI切换失败: ${e.message}")
            e.printStackTrace()
        }
    }
}
