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
            // HDMI模式：切换到HDMI输入
            switchToHdmi(policy.targetHdmiPort)
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
     */
    fun prepareForNewPolicy(policy: LaunchPolicy) {
        val keepPackages = mutableListOf<String>()

        when (policy.mode) {
            "app" -> {
                keepPackages.add(policy.targetAppPackage)
            }
            "hdmi" -> {
                keepPackages.add(HDMI_TV_PLAYER_PACKAGE)
            }
        }

        cleanupBackgroundApps(keepPackages)
    }

    /**
     * 启动指定包名的APP - 公开方法
     */
    fun launchApp(packageName: String) {
        android.util.Log.d(TAG, "启动APP: $packageName")

        // 尝试多种启动方法
        val methods = listOf(
            { launchByIntent(packageName) },  // 标准启动方法
            { launchByMonkey(packageName) },  // 使用monkey命令
            { launchByAmCommand(packageName) }  // 使用am命令
        )

        for ((index, method) in methods.withIndex()) {
            try {
                if (method()) {
                    android.util.Log.d(TAG, "成功启动APP: $packageName (方法${index + 1})")
                    return
                }
            } catch (e: Exception) {
                android.util.Log.w(TAG, "启动方法${index + 1}失败: ${e.message}")
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
            launchApp(packageName)
        }
    }

    /**
     * 检测指定APP是否在运行
     */
    fun isAppRunning(packageName: String): Boolean {
        android.util.Log.d(TAG, "检查进程是否运行: $packageName")
        try {
            // 方法1：通过pidof命令检查
            try {
                val process = Runtime.getRuntime().exec(arrayOf("pidof", packageName))
                val reader = java.io.BufferedReader(java.io.InputStreamReader(process.inputStream))
                val output = reader.readLine()
                reader.close()
                process.waitFor()
                if (!output.isNullOrBlank()) {
                    android.util.Log.d(TAG, "通过pidof找到进程: $packageName (pid=$output)")
                    return true
                }
            } catch (e: Exception) {
                android.util.Log.d(TAG, "pidof命令失败: ${e.message}")
            }

            // 方法2：通过/proc文件系统检查
            try {
                val procDir = java.io.File("/proc")
                val dirs = procDir.listFiles() ?: emptyArray()
                for (dir in dirs) {
                    if (dir.isDirectory && dir.name.matches(Regex("\\d+"))) {
                        val cmdlineFile = java.io.File(dir, "cmdline")
                        if (cmdlineFile.exists()) {
                            try {
                                val cmdline = cmdlineFile.readText().trimEnd('\u0000')
                                if (cmdline == packageName || cmdline.contains(packageName)) {
                                    android.util.Log.d(TAG, "通过/proc找到进程: $cmdline")
                                    return true
                                }
                            } catch (e: Exception) {
                                // 忽略无法读取的文件
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                android.util.Log.d(TAG, "/proc检查失败: ${e.message}")
            }

            // 方法3：检查运行中的进程
            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val processes = am.runningAppProcesses
            if (processes != null) {
                for (process in processes) {
                    if (process.processName == packageName || process.processName.contains(packageName)) {
                        android.util.Log.d(TAG, "找到运行中的进程: ${process.processName}")
                        return true
                    }
                }
            }
        } catch (e: Exception) {
            android.util.Log.e(TAG, "检查进程异常: ${e.message}")
        }
        android.util.Log.d(TAG, "未找到进程: $packageName")
        return false
    }

    /**
     * 切换到HDMI输入 - 使用Intent和模拟按键
     */
    private fun switchToHdmi(port: Int) {
        android.util.Log.d(TAG, "========== 开始切换到HDMI$port ==========")

        try {
            // 方法1: 使用Intent直接启动外部信号源选择界面
            android.util.Log.d(TAG, "方法1: 使用Intent打开信号源选择界面")

            try {
                val intent = Intent("com.xiaomi.mitv.tvplayer.EXTSRC_PLAY")
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(intent)
                android.util.Log.d(TAG, "Intent启动成功")
            } catch (e: Exception) {
                android.util.Log.w(TAG, "Intent启动失败: ${e.message}")
                // 尝试备用方法
                val intent = context.packageManager.getLaunchIntentForPackage(HDMI_TV_PLAYER_PACKAGE)
                if (intent != null) {
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    context.startActivity(intent)
                }
            }

            // 等待界面打开
            Thread.sleep(2500)

            // 检查当前焦点
            val currentPackage = getCurrentFocusPackage()
            android.util.Log.d(TAG, "当前焦点应用: $currentPackage")

            if (currentPackage?.contains("tvplayer") == true || currentPackage?.contains("External") == true) {
                android.util.Log.d(TAG, "信号源选择界面已打开，开始导航到HDMI$port")

                // 使用方向键导航到指定HDMI输入
                // 小米电视信号源列表：通常第一行是TV/DTV，然后是HDMI1, HDMI2, HDMI3等

                // 先按几次UP确保在最顶部
                for (i in 1..5) {
                    Runtime.getRuntime().exec(arrayOf("input", "keyevent", "19")).waitFor()  // DPAD_UP
                    Thread.sleep(150)
                }
                Thread.sleep(500)

                // 向下导航：HDMI1通常是第2个选项（TV之后）
                val downCount = port  // HDMI1: 1次, HDMI2: 2次, HDMI3: 3次
                for (i in 1..downCount) {
                    Runtime.getRuntime().exec(arrayOf("input", "keyevent", "20")).waitFor()  // DPAD_DOWN
                    Thread.sleep(200)
                }

                Thread.sleep(500)

                // 确认选择
                Runtime.getRuntime().exec(arrayOf("input", "keyevent", "23")).waitFor()  // DPAD_CENTER
                android.util.Log.d(TAG, "已确认选择HDMI$port")

                Thread.sleep(1500)

                // 验证结果
                val finalPackage = getCurrentFocusPackage()
                android.util.Log.d(TAG, "HDMI切换完成，当前焦点: $finalPackage")
                android.util.Log.d(TAG, "========== HDMI$port 切换完成 ==========")
                return
            }

            android.util.Log.w(TAG, "信号源界面未打开，尝试备用方法")

        } catch (e: Exception) {
            android.util.Log.e(TAG, "HDMI切换异常: ${e.message}")
            e.printStackTrace()
        }

        android.util.Log.d(TAG, "========== HDMI切换流程结束 ==========")
    }

    private fun launchByIntent(packageName: String): Boolean {
        val launchIntent = context.packageManager.getLaunchIntentForPackage(packageName)
        if (launchIntent != null) {
            launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(launchIntent)
            return true
        }
        return false
    }

    private fun launchByMonkey(packageName: String): Boolean {
        try {
            val process = Runtime.getRuntime().exec(arrayOf("monkey", "-p", packageName, "-c", "android.intent.category.LAUNCHER", "1"))
            val exitCode = process.waitFor()
            return exitCode == 0
        } catch (e: Exception) {
            return false
        }
    }

    private fun launchByAmCommand(packageName: String): Boolean {
        val activities = listOf(
            ".MainActivity",
            ".SplashActivity",
            ".HomeActivity",
            ".LauncherActivity",
            ".TVMainActivity",
            ".TVHomeActivity",
            ".Main"
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

    private fun getCurrentFocusPackage(): String? {
        return try {
            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val tasks = am.getRunningTasks(1)
            if (tasks != null && tasks.isNotEmpty()) {
                tasks[0].topActivity?.packageName
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }
}
