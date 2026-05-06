package com.company.tvlauncher

import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.app.ActivityManager

class LauncherExecutor(private val context: Context) {

    companion object {
        private const val TAG = "LauncherExecutor"
        const val HDMI_TV_PLAYER_PACKAGE = "com.xiaomi.mitv.tvplayer"

        // 追踪最近一次启动目标APP的时间，防止保活服务反复重启
        private var lastLaunchTimeMs: Long = 0
        private const val LAUNCH_COOLDOWN_MS = 15_000L // 启动后15秒内不再重复启动

        /** 记录启动时间 */
        fun recordLaunchTime() {
            lastLaunchTimeMs = System.currentTimeMillis()
        }

        /** 是否在启动冷却期 */
        fun isInLaunchCooldown(): Boolean {
            return System.currentTimeMillis() - lastLaunchTimeMs < LAUNCH_COOLDOWN_MS
        }
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
        recordLaunchTime()

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
        recordLaunchTime()

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
     *
     * 在SELinux Enforcing + MIUI的Android TV上，跨进程检测全部被阻止：
     * - pidof: 无权限
     * - /proc/[pid]/cmdline: Permission denied
     * - getRunningTasks: 被MIUI BLOCK-MONITOR阻止
     * - runningAppProcesses: 只返回自己
     *
     * 可靠的检测策略：
     * 1. 如果Launcher自己在前台 → 目标APP不在运行（需要启动）
     * 2. 如果Launcher在后台 → 目标APP很可能在前台运行（不需要重启）
     * 3. 启动冷却期：刚启动过的APP不做重复检测
     */
    fun isAppRunning(packageName: String): Boolean {
        android.util.Log.d(TAG, "检查进程是否运行: $packageName")

        // 启动冷却期：刚启动过的APP不做重复检测，避免启动→检测→重启的死循环
        if (isInLaunchCooldown()) {
            val remaining = (LAUNCH_COOLDOWN_MS - (System.currentTimeMillis() - lastLaunchTimeMs)) / 1000
            android.util.Log.d(TAG, "启动冷却期中(剩余${remaining}秒)，判定为运行中: $packageName")
            return true
        }

        // 核心判断：检查Launcher自身是否在前台
        // 作为HOME应用，如果Launcher在前台，说明目标APP没有运行
        // 如果Launcher在后台，说明有其他应用（目标APP）在前台
        val isLauncherForeground = isLauncherInForeground()
        if (!isLauncherForeground) {
            android.util.Log.d(TAG, "Launcher在后台，目标APP大概率在运行: $packageName")
            return true
        }

        // Launcher在前台，尝试其他检测方式作为补充
        try {
            // 方法1：通过pidof命令检查
            // 注意：部分Android版本(如6.0)的pidof会忽略包名参数，返回所有进程PID
            // 正常pidof应返回单个PID或少数几个(同包名多进程)，如果返回大量PID说明命令无效
            try {
                val process = Runtime.getRuntime().exec(arrayOf("pidof", packageName))
                val reader = java.io.BufferedReader(java.io.InputStreamReader(process.inputStream))
                val output = reader.readLine()
                reader.close()
                process.waitFor()
                if (!output.isNullOrBlank()) {
                    val pidCount = output.trim().split(Regex("\\s+")).size
                    if (pidCount <= 3) {
                        // 正常情况：1-3个PID（主进程+可能的子进程）
                        android.util.Log.d(TAG, "通过pidof找到进程: $packageName (pid=$output)")
                        return true
                    } else {
                        // 异常：返回了大量PID，说明pidof忽略了包名参数，结果不可信
                        android.util.Log.d(TAG, "pidof返回${pidCount}个PID，忽略不可信结果，继续其他检测")
                    }
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

            // 方法3：检查运行中的进程（Android 9+可能只返回自己）
            try {
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
                android.util.Log.d(TAG, "runningAppProcesses检查失败: ${e.message}")
            }
        } catch (e: Exception) {
            android.util.Log.e(TAG, "检查进程异常: ${e.message}")
        }

        android.util.Log.d(TAG, "Launcher在前台且目标APP未被检测到，判定未运行: $packageName")
        return false
    }

    /**
     * 检查Launcher自身是否在前台
     * 通过SharedPreferences中保存的前台状态判断（由MainActivity的onResume/onPause更新）
     */
    private fun isLauncherInForeground(): Boolean {
        val prefs = context.getSharedPreferences("tv_policy", Context.MODE_PRIVATE)
        return prefs.getBoolean("launcher_foreground", true)
    }

    /**
     * 切换到HDMI输入 - 使用HdmiActivity + TvView API
     *
     * 方式1: 启动HdmiActivity，使用TvView直接调谐到HDMI输入
     *   这是Android TV标准的HDMI切换方式，通过TvInputManager/TvView与
     *   HdmiInputService建立会话，直接显示HDMI信号。
     *   支持精确指定HDMI1/HDMI2/HDMI3端口。
     *   已适配4种芯片平台: Amlogic/Droidlogic, MediaTek, MStar, Realtek
     *
     * 方式2: SETUP_INPUTS Intent (Android 9+备用)
     * 方式3: 小米电视专用 EXTSRC_PLAY (备用)
     * 方式4: 通过tvplayer启动 (兜底)
     */
    private fun switchToHdmi(port: Int) {
        android.util.Log.d(TAG, "========== 开始切换到HDMI$port ==========")

        // 方式1: 启动HdmiActivity (TvView API方式)
        // HdmiActivity内部会自动检测芯片类型，选择正确的inputId
        try {
            android.util.Log.d(TAG, "方式1: 启动HdmiActivity，port=$port")
            val intent = Intent(context, HdmiActivity::class.java)
            intent.putExtra(HdmiActivity.EXTRA_HDMI_PORT, port)
            // FLAG_ACTIVITY_NEW_TASK: Service/Receiver启动Activity时必须
            // FLAG_ACTIVITY_CLEAR_TOP + FLAG_ACTIVITY_SINGLE_TOP: 复用singleTask实例，触发onNewIntent
            intent.addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or
                Intent.FLAG_ACTIVITY_CLEAR_TOP or
                Intent.FLAG_ACTIVITY_SINGLE_TOP
            )
            context.startActivity(intent)
            android.util.Log.d(TAG, "HdmiActivity已启动")
            android.util.Log.d(TAG, "========== HDMI$port 切换完成(HdmiActivity) ==========")
            return
        } catch (e: Exception) {
            android.util.Log.w(TAG, "方式1失败(HdmiActivity): ${e.message}")
        }

        // 方式2: SETUP_INPUTS Intent (Android 9+)
        try {
            // 构造Droidlogic inputId用于SETUP_INPUTS备用方案
            val droidlogicInputId = when (port) {
                1 -> "com.droidlogic.tvinput/.services.Hdmi1InputService/HW5"
                2 -> "com.droidlogic.tvinput/.services.Hdmi2InputService/HW6"
                3 -> "com.droidlogic.tvinput/.services.Hdmi3InputService/HW7"
                else -> "com.droidlogic.tvinput/.services.Hdmi1InputService/HW5"
            }
            android.util.Log.d(TAG, "方式2: 使用SETUP_INPUTS切换: $droidlogicInputId")
            val intent = Intent("android.media.tv.action.SETUP_INPUTS")
            intent.putExtra("from_tv_source", true)
            intent.putExtra("android.media.tv.extra.INPUT_ID", droidlogicInputId)
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            android.util.Log.d(TAG, "========== HDMI$port 切换完成(SETUP_INPUTS) ==========")
            return
        } catch (e: Exception) {
            android.util.Log.w(TAG, "方式2失败(SETUP_INPUTS): ${e.message}")
        }

        // 方式3: 小米电视专用 EXTSRC_PLAY
        try {
            android.util.Log.d(TAG, "方式3: 使用小米EXTSRC_PLAY切换")
            val intent = Intent("com.xiaomi.mitv.tvplayer.EXTSRC_PLAY")
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            android.util.Log.d(TAG, "========== HDMI$port 切换完成(EXTSRC) ==========")
            return
        } catch (e: Exception) {
            android.util.Log.w(TAG, "方式3失败(EXTSRC): ${e.message}")
        }

        // 方式4: 启动tvplayer
        try {
            android.util.Log.d(TAG, "方式4: 启动tvplayer")
            val intent = context.packageManager.getLaunchIntentForPackage(HDMI_TV_PLAYER_PACKAGE)
            if (intent != null) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(intent)
                android.util.Log.d(TAG, "========== HDMI$port 切换完成(tvplayer) ==========")
                return
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "方式4失败(tvplayer): ${e.message}")
        }

        android.util.Log.e(TAG, "========== 所有HDMI切换方式均失败 ==========")
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

    /**
     * 热恢复：把后台APP拉到前台，不重新创建Activity
     * 使用FLAG_ACTIVITY_REORDER_TO_FRONT保留APP状态（如投屏码），失败则回退到launchApp
     */
    fun bringAppToFront(packageName: String) {
        android.util.Log.d(TAG, "热恢复APP到前台: $packageName")
        recordLaunchTime()

        // 方法1: Intent + FLAG_ACTIVITY_REORDER_TO_FRONT — 保留Activity状态
        try {
            val launchIntent = context.packageManager.getLaunchIntentForPackage(packageName)
            if (launchIntent != null) {
                launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
                android.util.Log.d(TAG, "尝试REORDER_TO_FRONT: $packageName, intent=${launchIntent.component}")
                context.startActivity(launchIntent)
                android.util.Log.d(TAG, "REORDER_TO_FRONT恢复成功: $packageName")
                return
            } else {
                android.util.Log.w(TAG, "getLaunchIntentForPackage返回null: $packageName")
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "REORDER_TO_FRONT失败: ${e.message}")
        }

        // 方法2: moveTaskToFront
        try {
            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val tasks = am.getRunningTasks(10)
            if (tasks != null) {
                for (task in tasks) {
                    if (task.topActivity?.packageName == packageName) {
                        am.moveTaskToFront(task.id, 0)
                        android.util.Log.d(TAG, "moveTaskToFront成功: $packageName (taskId=${task.id})")
                        return
                    }
                }
            }
        } catch (e: Exception) {
            android.util.Log.w(TAG, "moveTaskToFront失败: ${e.message}")
        }

        // 方法3: 回退到标准launchApp（冷启动）
        android.util.Log.d(TAG, "热恢复失败，回退到冷启动: $packageName")
        launchApp(packageName)
    }
}
