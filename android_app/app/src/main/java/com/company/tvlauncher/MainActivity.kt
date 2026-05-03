package com.company.tvlauncher

import android.app.ActivityManager
import android.app.AlertDialog
import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.work.Constraints
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.CountDownLatch

class MainActivity : AppCompatActivity() {
    private val ioExecutor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private var lastPolicyExecutionTime = 0L
    private val EXECUTION_COOLDOWN = 5000L // 5 seconds cooldown to prevent loops

    // 保活检查的Handler和Runnable
    private var keepAliveHandler: Handler? = null
    private var keepAliveRunnable: Runnable? = null

    // 时间更新Handler
    private var timeUpdateHandler: Handler? = null
    private var timeUpdateRunnable: Runnable? = null

    private val policyUpdateReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == "com.company.tvlauncher.POLICY_UPDATED") {
                android.util.Log.d("MainActivity", "===== 收到策略更新广播 =====")
                // 先同步最新的策略状态（包括暂停状态），再执行
                ioExecutor.execute {
                    val policyStore = PolicyStore(this@MainActivity)
                    val api = RemoteApi(this@MainActivity, policyStore)
                    val net = NetworkInfoProvider(this@MainActivity).collect()

                    // 立即执行心跳同步，获取最新策略和暂停状态
                    val heartbeatSuccess = api.heartbeat(net)
                    val isPaused = policyStore.isPolicyPaused()
                    android.util.Log.d("MainActivity", "心跳同步完成: success=$heartbeatSuccess, isPaused=$isPaused")

                    // 在主线程检查暂停状态并决定是否执行策略
                    mainHandler.post {
                        refreshStatus(policyStore)
                        if (isPaused) {
                            android.util.Log.d("MainActivity", "===== 策略已暂停，切回主页 =====")
                            // 暂停策略时：把Launcher带到前台，停止HDMI，关闭投屏APP
                            bringLauncherToFront()
                        } else {
                            android.util.Log.d("MainActivity", "===== 策略未暂停，执行策略 =====")
                            forceExecutePolicy(policyStore, force = true, userTriggered = true)
                        }
                    }
                }
            }
        }
    }

    // HDMI状态变化广播接收器
    private val hdmiStatusReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == HdmiReceiver.ACTION_HDMI_STATUS_CHANGED) {
                val connected = intent.getBooleanExtra(HdmiReceiver.EXTRA_HDMI_CONNECTED, false)
                android.util.Log.d("MainActivity", "===== HDMI状态变化: connected=$connected =====")
                handleHdmiStatusChanged(connected)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // 从轻量启动主题切换到完整主题（防止Android 6冷启动白屏）
        setTheme(R.style.Theme_TvLauncher_Fullscreen)
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // 请求位置权限（Android 6+读取WiFi SSID需要）
        requestLocationPermission()

        val policyStore = PolicyStore(this)
        refreshStatus(policyStore)

        findViewById<LinearLayout>(R.id.openSettingsBtn).setOnClickListener {
            showPasswordDialog(policyStore)
        }
        findViewById<LinearLayout>(R.id.executeBtn).setOnClickListener {
            launchTargetOnce(policyStore)
        }

        // 注册策略更新广播接收器
        val filter = IntentFilter("com.company.tvlauncher.POLICY_UPDATED")
        registerReceiver(policyUpdateReceiver, filter)

        // 注册HDMI状态变化广播接收器
        val hdmiFilter = IntentFilter(HdmiReceiver.ACTION_HDMI_STATUS_CHANGED)
        registerReceiver(hdmiStatusReceiver, hdmiFilter)

        // 检查HDMI初始状态（APP启动时HDMI可能已接入）
        checkInitialHdmiState()

        // Schedule periodic sync every 15 mins (minimum allowed by WorkManager)
        schedulePeriodicSync()

        // 启动前台服务，防止被系统清理
        val foregroundIntent = Intent(this, KeepAliveForegroundService::class.java)
        startService(foregroundIntent)

        // 启动时间更新
        startTimeUpdate()
    }

    private fun startTimeUpdate() {
        timeUpdateHandler = Handler(Looper.getMainLooper())
        timeUpdateRunnable = object : Runnable {
            override fun run() {
                val timeText = findViewById<TextView>(R.id.timeText)
                val timeFormat = java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault())
                timeText.text = timeFormat.format(java.util.Date())
                timeUpdateHandler?.postDelayed(this, 1000) // 每秒更新
            }
        }
        timeUpdateHandler?.post(timeUpdateRunnable!!)
    }

    /**
     * 请求位置权限（Android 6+读取WiFi SSID需要ACCESS_COARSE_LOCATION）
     */
    private fun requestLocationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)
                != PackageManager.PERMISSION_GRANTED
            ) {
                requestPermissions(
                    arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION),
                    100
                )
            }
        }
    }

    /**
     * 手动启动目标APP一次（按钮点击）
     * 不管策略是否暂停，都启动目标APP一次。
     * 不启动保活服务，不改变暂停状态 —— 仅启动一次。
     * 用途：测试目标APP是否正常，或在策略被误暂停时临时启动一次。
     */
    private fun launchTargetOnce(policyStore: PolicyStore) {
        val policy = policyStore.getPolicy()

        if (!isPolicyValid(policy)) {
            showNoPolicyDialog()
            return
        }

        val executor = LauncherExecutor(this)
        val isPaused = policyStore.isPolicyPaused()

        when (policy.mode) {
            "app" -> {
                android.util.Log.d("MainActivity", "手动启动目标APP一次: ${policy.targetAppPackage} (暂停=$isPaused)")
                executor.launchApp(policy.targetAppPackage)
            }
            "hdmi" -> {
                android.util.Log.d("MainActivity", "手动切换HDMI一次: HDMI${policy.targetHdmiPort} (暂停=$isPaused)")
                ioExecutor.execute {
                    executor.execute(policy)
                }
            }
        }
    }

    private fun bringLauncherToFront() {
        // 暂停策略时：关闭HDMI画面，把Launcher带到前台
        try {
            // 如果HdmiActivity在前台，先关掉它
            val hdmiIntent = Intent(this, HdmiActivity::class.java)
            hdmiIntent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            hdmiIntent.putExtra("finish", true)
            startActivity(hdmiIntent)
        } catch (_: Exception) {}

        // 把Launcher自身带到前台
        val launcherIntent = Intent(this, MainActivity::class.java)
        launcherIntent.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        startActivity(launcherIntent)
    }

    private fun forceExecutePolicy(policyStore: PolicyStore, force: Boolean = false, userTriggered: Boolean = false, forceRestart: Boolean = false) {
        // 先检查策略是否暂停（从SharedPreferences重新读取）
        val isPaused = policyStore.isPolicyPaused()
        android.util.Log.d("MainActivity", "forceExecutePolicy: isPaused=$isPaused")

        if (isPaused) {
            android.util.Log.d("MainActivity", "===== 策略已暂停，跳过执行 =====")
            refreshStatus(policyStore)
            return
        }

        val policy = policyStore.getPolicy()

        // 检查策略是否有效
        if (!isPolicyValid(policy)) {
            showNoPolicyDialog()
            return
        }

        val now = System.currentTimeMillis()

        // 用户主动触发（如按返回键）：立即执行，重置冷却时间
        if (userTriggered) {
            android.util.Log.d("MainActivity", "用户主动触发策略执行")
            lastPolicyExecutionTime = now
            lastHdmiSwitchTime = now
        } else {
            // 自动触发：需要检查冷却期
            // HDMI模式：检查30秒冷却期（避免自动循环）
            if (policy.mode == "hdmi" && now - lastHdmiSwitchTime < HDMI_SWITCH_COOLDOWN) {
                android.util.Log.d("MainActivity", "HDMI切换冷却中(${(now - lastHdmiSwitchTime)/1000}秒)，跳过自动执行")
                return
            }

            // 防抖检查：非强制模式下，5秒内不重复执行
            if (!force && now - lastPolicyExecutionTime < EXECUTION_COOLDOWN) {
                android.util.Log.d("MainActivity", "策略执行冷却中(${(now - lastPolicyExecutionTime)/1000}秒)，跳过")
                return
            }

            // 更新执行时间
            lastPolicyExecutionTime = now
            lastHdmiSwitchTime = now
        }

        // 策略更新时强制清理所有后台应用，但保留目标APP和系统应用
        val keepPackages = mutableListOf<String>()

        when (policy.mode) {
            "app" -> {
                // APP模式：保留目标APP
                keepPackages.add(policy.targetAppPackage)
                android.util.Log.d("MainActivity", "APP模式策略执行，保留: ${policy.targetAppPackage}")
            }
            "hdmi" -> {
                // HDMI模式：保留小米电视播放器APP，这是HDMI切换所必需的
                keepPackages.add(LauncherExecutor.HDMI_TV_PLAYER_PACKAGE)
                android.util.Log.d("MainActivity", "HDMI模式策略执行，保留: ${LauncherExecutor.HDMI_TV_PLAYER_PACKAGE}")
            }
        }

        // 清理后台应用，但保留指定的包名
        val executor = LauncherExecutor(this)
        executor.cleanupBackgroundApps(keepPackages)

        // 执行新策略 - HDMI模式现在使用Intent直接切换，无需后台线程
        if (policy.mode == "hdmi") {
            android.util.Log.d("MainActivity", "HDMI模式执行切换")
            executor.execute(policy)
        } else if (policy.mode == "app" && forceRestart) {
            // APP模式 + 需要强制重启：先停止再启动（解决投屏码刷新问题）
            android.util.Log.d("MainActivity", "APP模式强制重启: ${policy.targetAppPackage}")
            executor.forceStopAndRestart(policy.targetAppPackage)
        } else {
            executor.execute(policy)
        }

        // 启动保活服务，确保目标APP持续运行
        startKeepAliveService(policy)

        // 同时启动前台服务
        val foregroundIntent = Intent(this, KeepAliveForegroundService::class.java)
        startService(foregroundIntent)

        android.util.Log.d("MainActivity", "策略已执行: ${policy.mode}模式")
    }

    private fun isPolicyValid(policy: LaunchPolicy): Boolean {
        // 检查策略是否有效
        // 1. 如果是app模式，目标包名不能为空且不能是默认值
        // 2. 如果是hdmi模式，端口号必须大于0
        return when (policy.mode) {
            "app" -> {
                val targetApp = policy.targetAppPackage
                !targetApp.isNullOrBlank() &&
                targetApp != "com.example.cast" &&
                targetApp != "com.android.settings"
            }
            "hdmi" -> policy.targetHdmiPort > 0
            else -> false
        }
    }

    private fun showNoPolicyDialog() {
        AlertDialog.Builder(this)
            .setTitle("策略配置")
            .setMessage("暂无有效策略，5秒后返回主页")
            .setCancelable(false)
            .show()

        // 5秒后自动返回主页
        mainHandler.postDelayed({
            val intent = Intent(Intent.ACTION_MAIN)
            intent.addCategory(Intent.CATEGORY_HOME)
            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
            startActivity(intent)
        }, 5000)
    }

    private fun cleanupBackgroundApps(excludePackage: String) {
        try {
            val am = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val tasks = am.runningAppProcesses
            if (tasks != null) {
                for (task in tasks) {
                    if (task.processName != packageName && task.processName != excludePackage) {
                        am.killBackgroundProcesses(task.processName)
                    }
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun cleanupBackgroundApps(keepPackages: List<String> = emptyList()) {
        try {
            val am = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val tasks = am.runningAppProcesses
            if (tasks != null) {
                for (task in tasks) {
                    val processName = task.processName

                    // 检查是否需要保留此进程
                    val shouldKeep = keepPackages.any { keepPackage ->
                        processName.contains(keepPackage)
                    }

                    // 只清理非系统应用、非本应用、且不在保留列表中的应用
                    if (processName != packageName &&
                        !processName.startsWith("com.android.") &&
                        !processName.startsWith("android.") &&
                        !shouldKeep) {
                        am.killBackgroundProcesses(processName)
                    }
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun showPasswordDialog(policyStore: PolicyStore) {
        val input = EditText(this).apply {
            inputType = android.text.InputType.TYPE_CLASS_NUMBER or
                        android.text.InputType.TYPE_NUMBER_VARIATION_PASSWORD
            hint = "请输入4位管理密码"
        }
        val container = FrameLayout(this).apply {
            val params = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
            )
            params.setMargins(60, 20, 60, 20)
            addView(input, params)
        }

        AlertDialog.Builder(this)
            .setTitle("管理锁")
            .setMessage("输入密码以进入设置")
            .setView(container)
            .setPositiveButton("确认") { _, _ ->
                val pwd = input.text.toString()
                if (pwd == policyStore.getSettingsPassword()) {
                    startActivity(Intent(this, SettingsActivity::class.java))
                }
            }
            .setNegativeButton("取消", null)
            .show()
    }

    override fun onResume() {
        super.onResume()
        // 更新Launcher前台状态（供isAppRunning检测使用）
        getSharedPreferences("tv_policy", Context.MODE_PRIVATE)
            .edit().putBoolean("launcher_foreground", true).apply()
        android.util.Log.d("MainActivity", "Launcher前台状态: true")

        val policyStore = PolicyStore(this)
        refreshStatus(policyStore)

        // 启动前台服务，防止被系统清理
        val foregroundIntent = Intent(this, KeepAliveForegroundService::class.java)
        startService(foregroundIntent)

        val now = System.currentTimeMillis()
        val policy = policyStore.getPolicy()

        // 立即执行策略，不等待网络I/O
        // 开机时网络未就绪，等网络会浪费数秒黑屏时间
        if (isPolicyValid(policy) && !policyStore.isPolicyPaused()
            && !policyStore.isEscapeModeActive()
            && now - lastPolicyExecutionTime > EXECUTION_COOLDOWN) {
            android.util.Log.d("MainActivity", "${policy.mode}模式：立即执行策略，不等待网络")
            lastPolicyExecutionTime = now
            lastHdmiSwitchTime = now

            val executor = LauncherExecutor(this)
            when (policy.mode) {
                "hdmi" -> executor.execute(policy)
                "app" -> executor.launchApp(policy.targetAppPackage)
            }
            startKeepAliveService(policy)
        }

        // 网络I/O放后台异步执行，不阻塞策略执行
        ioExecutor.execute {
            val net = NetworkInfoProvider(this).collect()
            val api = RemoteApi(this, policyStore)

            // 注册流程：没有token就注册，有心跳失败就清除token重新注册
            val hasToken = policyStore.getDeviceToken() != null
            if (!hasToken) {
                val registered = api.registerIfNeeded("MeetingTV", net)
                if (!registered) {
                    android.util.Log.w("MainActivity", "注册失败，请检查服务器地址和网络")
                    mainHandler.post { refreshStatus(policyStore) }
                    return@execute
                }
            }

            var heartbeatSuccess = api.heartbeat(net)
            if (!heartbeatSuccess) {
                // 心跳失败：token可能已失效（设备被移除），清除后重新注册
                android.util.Log.w("MainActivity", "心跳失败，清除token并重新注册")
                policyStore.clearDeviceToken()
                val reRegistered = api.registerIfNeeded("MeetingTV", net)
                if (reRegistered) {
                    heartbeatSuccess = api.heartbeat(net)
                }
            }

            // 同步完成后，在主线程更新状态
            mainHandler.post {
                refreshStatus(policyStore)
                // 策略已在onResume开头立即执行，此处只更新UI状态
            }
        }
    }

    override fun onPause() {
        super.onPause()
        // 更新Launcher前台状态（供isAppRunning检测使用）
        getSharedPreferences("tv_policy", Context.MODE_PRIVATE)
            .edit().putBoolean("launcher_foreground", false).apply()
        android.util.Log.d("MainActivity", "Launcher前台状态: false")

        // 启动保活服务，确保策略APP一直在前台
        val policyStore = PolicyStore(this)
        val policy = policyStore.getPolicy()
        if (isPolicyValid(policy)) {
            startKeepAliveService(policy)
        }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            val policyStore = PolicyStore(this)
            if (policyStore.isEscapeModeActive() || !policyStore.getKioskEnabled()) {
                return super.onKeyDown(keyCode, event)
            }
            // 用户按返回键 - 触发保活，重置冷却时间
            // APP模式下强制重启APP（解决投屏码刷新问题）
            val policy = policyStore.getPolicy()
            val forceRestart = policy.mode == "app"
            forceExecutePolicy(policyStore, userTriggered = true, forceRestart = forceRestart)
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onUserLeaveHint() {
        // This is called when Home key is pressed or user switches tasks
        super.onUserLeaveHint()
        // We can't block Home easily without being a System Home app,
        // but since we are a Launcher, we will be resumed immediately if we are the default.
    }

    private fun showUpdateDialog(updateInfo: JSONObject) {
        val version = updateInfo.optString("latest_version")
        val url = updateInfo.optString("url")
        AlertDialog.Builder(this)
            .setTitle("系统更新")
            .setMessage("发现新版本 $version，建议立即更新以获得更好体验。")
            .setPositiveButton("立即下载") { _, _ ->
                val intent = Intent(Intent.ACTION_VIEW, android.net.Uri.parse(url))
                startActivity(intent)
            }
            .setNegativeButton("稍后", null)
            .show()
    }

    private fun schedulePeriodicSync() {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val syncRequest = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(constraints)
            .build()

        WorkManager.getInstance(applicationContext).enqueueUniquePeriodicWork(
            "DeviceSync",
            androidx.work.ExistingPeriodicWorkPolicy.KEEP,
            syncRequest
        )
    }

    // Kiosk Mode: Handled via onKeyDown
    override fun onBackPressed() {
        val policyStore = PolicyStore(this)
        if (policyStore.isEscapeModeActive() || !policyStore.getKioskEnabled()) {
            super.onBackPressed()
        }
    }

    private var lastHdmiSwitchTime = 0L
    private val HDMI_SWITCH_COOLDOWN = 30000L // 30秒内不重复检查HDMI保活

    /**
     * 处理HDMI状态变化
     * HDMI接入：保存当前策略，自动切换到HDMI1
     * HDMI断开：恢复之前的策略
     */
    private fun handleHdmiStatusChanged(connected: Boolean) {
        val policyStore = PolicyStore(this)

        // 检查HDMI自动切换功能是否开启
        if (!policyStore.isHdmiAutoSwitchEnabled()) {
            android.util.Log.d("MainActivity", "HDMI自动切换功能已关闭，忽略HDMI事件")
            return
        }

        if (connected) {
            // HDMI接入
            val currentPolicy = policyStore.getPolicy()

            // 如果当前已经是HDMI模式，不需要切换
            if (currentPolicy.mode == "hdmi") {
                android.util.Log.d("MainActivity", "当前已是HDMI模式，无需自动切换")
                return
            }

            // 如果策略已暂停，不触发自动切换
            if (policyStore.isPolicyPaused()) {
                android.util.Log.d("MainActivity", "策略已暂停，不触发HDMI自动切换")
                return
            }

            // 保存当前策略，标记为HDMI自动切换
            policyStore.savePreHdmiPolicy(currentPolicy)
            policyStore.setHdmiAutoSwitched(true)

            // 切换到HDMI1策略
            val hdmiPolicy = LaunchPolicy(mode = "hdmi", targetHdmiPort = 1)
            policyStore.savePolicy(hdmiPolicy)

            android.util.Log.d("MainActivity", "HDMI接入，自动切换到HDMI1。原策略: ${currentPolicy.mode}/${currentPolicy.targetAppPackage}")

            // 执行HDMI1策略
            forceExecutePolicy(policyStore, force = true, userTriggered = true)
        } else {
            // HDMI断开
            if (!policyStore.isHdmiAutoSwitched()) {
                android.util.Log.d("MainActivity", "HDMI断开，但不是自动切换的，不恢复策略")
                return
            }

            // 恢复之前的策略
            val prePolicy = policyStore.getPreHdmiPolicy()
            if (prePolicy != null) {
                policyStore.savePolicy(prePolicy)
                policyStore.setHdmiAutoSwitched(false)
                policyStore.clearPreHdmiPolicy()

                android.util.Log.d("MainActivity", "HDMI断开，恢复原策略: ${prePolicy.mode}/${prePolicy.targetAppPackage}")

                // 执行恢复的策略
                forceExecutePolicy(policyStore, force = true, userTriggered = true)
            } else {
                // 没有之前的策略记录，只清除标记
                policyStore.setHdmiAutoSwitched(false)
                policyStore.clearPreHdmiPolicy()
                android.util.Log.d("MainActivity", "HDMI断开，无之前的策略记录")
            }
        }

        refreshStatus(policyStore)
    }

    /**
     * 检查HDMI初始状态
     * APP启动时HDMI可能已经接入，通过Sticky Intent获取当前状态
     */
    private fun checkInitialHdmiState() {
        try {
            val stickyIntent = registerReceiver(null, IntentFilter("android.intent.action.HDMI_PLUGGED"))
            if (stickyIntent != null) {
                val connected = stickyIntent.getBooleanExtra("state", false)
                android.util.Log.d("MainActivity", "HDMI初始状态: connected=$connected")

                if (connected) {
                    val policyStore = PolicyStore(this)
                    // 如果当前是APP模式且HDMI已接入，自动切换到HDMI1
                    val currentPolicy = policyStore.getPolicy()
                    if (currentPolicy.mode == "app" &&
                        policyStore.isHdmiAutoSwitchEnabled() &&
                        !policyStore.isPolicyPaused()) {

                        policyStore.savePreHdmiPolicy(currentPolicy)
                        policyStore.setHdmiAutoSwitched(true)

                        val hdmiPolicy = LaunchPolicy(mode = "hdmi", targetHdmiPort = 1)
                        policyStore.savePolicy(hdmiPolicy)

                        android.util.Log.d("MainActivity", "启动时HDMI已接入，自动切换到HDMI1")

                        // 延迟执行，等待Activity完全启动
                        mainHandler.postDelayed({
                            forceExecutePolicy(PolicyStore(this), force = true, userTriggered = true)
                            refreshStatus(PolicyStore(this))
                        }, 3000)
                    }
                }
            } else {
                // 尝试读取/sys文件作为备用
                try {
                    val stateFile = java.io.File("/sys/class/switch/hdmirx_hpd/state")
                    if (stateFile.exists()) {
                        val state = stateFile.readText().trim()
                        android.util.Log.d("MainActivity", "HDMI初始状态(sysfs): $state")
                        if (state == "1") {
                            val policyStore = PolicyStore(this)
                            val currentPolicy = policyStore.getPolicy()
                            if (currentPolicy.mode == "app" &&
                                policyStore.isHdmiAutoSwitchEnabled() &&
                                !policyStore.isPolicyPaused()) {

                                policyStore.savePreHdmiPolicy(currentPolicy)
                                policyStore.setHdmiAutoSwitched(true)

                                val hdmiPolicy = LaunchPolicy(mode = "hdmi", targetHdmiPort = 1)
                                policyStore.savePolicy(hdmiPolicy)

                                android.util.Log.d("MainActivity", "启动时HDMI已接入(sysfs)，自动切换到HDMI1")

                                mainHandler.postDelayed({
                                    forceExecutePolicy(PolicyStore(this), force = true, userTriggered = true)
                                    refreshStatus(PolicyStore(this))
                                }, 3000)
                            }
                        }
                    }
                } catch (e: Exception) {
                    android.util.Log.d("MainActivity", "读取HDMI sysfs状态失败: ${e.message}")
                }
            }
        } catch (e: Exception) {
            android.util.Log.e("MainActivity", "检查HDMI初始状态失败: ${e.message}")
        }
    }

    // 不需要保活干预的应用列表（如浏览器、设置等）
    private val EXCLUDED_PACKAGES = listOf(
        "com.android.chrome",
        "com.android.browser",
        "com.emotn.browser",
        "com.ucbrowser.tv",
        "com.xiaomi.mitv.settings",
        "com.android.settings"
    )

    private fun startKeepAliveService(policy: LaunchPolicy) {
        // 停止之前的保活检查
        keepAliveHandler?.removeCallbacks(keepAliveRunnable!!)

        // 启动新的保活检查
        keepAliveHandler = Handler(Looper.getMainLooper())

        val executor = LauncherExecutor(this)

        keepAliveRunnable = object : Runnable {
            override fun run() {
                try {
                    // 首先检查暂停状态
                    val policyStore = PolicyStore(this@MainActivity)
                    if (policyStore.isPolicyPaused()) {
                        android.util.Log.d("MainActivity", "保活检查: 策略已暂停，跳过")
                        keepAliveHandler?.postDelayed(this, 5000)
                        return
                    }

                    // 检查当前焦点应用，如果是浏览器/设置等，不干预
                    val currentPackage = getCurrentFocusPackage()
                    if (currentPackage != null && EXCLUDED_PACKAGES.any { currentPackage.contains(it) }) {
                        android.util.Log.d("MainActivity", "当前在排除应用中($currentPackage)，跳过保活检查")
                        keepAliveHandler?.postDelayed(this, 30000)
                        return
                    }

                    when (policy.mode) {
                        "app" -> {
                            // APP模式：检查目标APP是否在前台运行
                            // 仅检查进程存在不够：用户按返回键后APP退到后台，进程还在但不在前台
                            // 正确做法：如果Launcher自己在前台，说明目标APP不在前台，需要重新拉起
                            val isLauncherFg = isLauncherInForegroundCheck()
                            if (isLauncherFg) {
                                // Launcher在前台 = 目标APP不在前台（可能退到后台或被关闭）
                                // 无论进程是否存在，都需要把目标APP拉到前台
                                android.util.Log.d("MainActivity", "Launcher在前台，目标APP不在前台，重新拉起: ${policy.targetAppPackage}")
                                executor.launchApp(policy.targetAppPackage)
                            } else {
                                // Launcher不在前台 = 有其他应用在前台
                                // 检查是否是目标APP，如果不是则需要拉起
                                val currentPkg = getCurrentFocusPackage()
                                if (currentPkg != null && currentPkg != policy.targetAppPackage && !EXCLUDED_PACKAGES.any { currentPkg.contains(it) }) {
                                    android.util.Log.d("MainActivity", "当前前台是 $currentPkg 而非目标APP，重新拉起: ${policy.targetAppPackage}")
                                    executor.launchApp(policy.targetAppPackage)
                                }
                                // 如果当前前台就是目标APP，不需要操作
                            }
                        }
                        "hdmi" -> {
                            // HDMI模式：只进行状态监控，不重复执行HDMI切换
                            // HDMI切换是一次性的，切换完成后不需要再干预

                            val now = System.currentTimeMillis()
                            val timeSinceSwitch = now - lastHdmiSwitchTime

                            // HDMI切换后30秒内不做任何保活检查，让系统稳定
                            if (timeSinceSwitch < HDMI_SWITCH_COOLDOWN) {
                                android.util.Log.d("MainActivity", "HDMI切换后冷却期(${timeSinceSwitch/1000}秒)，跳过保活检查")
                            } else {
                                // 冷却期后，只检查播放器进程是否存在，不重复切换
                                val isPlayerRunning = executor.isAppRunning(LauncherExecutor.HDMI_TV_PLAYER_PACKAGE)
                                android.util.Log.d("MainActivity", "HDMI保活检查: 播放器运行=$isPlayerRunning")

                                // 只有播放器完全被杀死时才启动（极罕见情况）
                                // 正常情况下HDMI信号源面板由系统UI控制，不需要保活
                            }
                        }
                    }
                } catch (e: Exception) {
                    android.util.Log.e("MainActivity", "保活检查异常: ${e.message}")
                    e.printStackTrace()
                }

                // 每30秒检查一次（大幅降低检查频率）
                keepAliveHandler?.postDelayed(this, 30000)
            }
        }

        // 延迟10秒后开始首次保活检查（给HDMI切换足够时间稳定）
        keepAliveHandler?.postDelayed(keepAliveRunnable!!, 10000)
    }

    private fun getCurrentFocusPackage(): String? {
        return try {
            val am = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
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
     * 检查Launcher自身是否在前台
     * 使用SharedPreferences中由onResume/onPause更新的状态
     */
    private fun isLauncherInForegroundCheck(): Boolean {
        val prefs = getSharedPreferences("tv_policy", Context.MODE_PRIVATE)
        return prefs.getBoolean("launcher_foreground", true)
    }

    override fun onDestroy() {
        super.onDestroy()
        // 清理保活Handler
        keepAliveHandler?.removeCallbacks(keepAliveRunnable!!)
        keepAliveHandler = null
        keepAliveRunnable = null

        // 清理时间更新Handler
        timeUpdateHandler?.removeCallbacks(timeUpdateRunnable!!)
        timeUpdateHandler = null
        timeUpdateRunnable = null

        // 注销广播接收器
        try {
            unregisterReceiver(policyUpdateReceiver)
        } catch (e: Exception) {
            // 忽略未注册的情况
        }
        try {
            unregisterReceiver(hdmiStatusReceiver)
        } catch (e: Exception) {
            // 忽略未注册的情况
        }
    }

    private fun refreshStatus(policyStore: PolicyStore) {
        val policy = policyStore.getPolicy()
        val token = policyStore.getDeviceToken()
        val isPaused = policyStore.isPolicyPaused()

        // 更新时间显示
        val timeText = findViewById<TextView>(R.id.timeText)
        val timeFormat = java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault())
        timeText.text = timeFormat.format(java.util.Date())

        // 更新状态文本（当前策略名称）
        val statusText = findViewById<TextView>(R.id.statusText)
        val policyName = when (policy.mode) {
            "app" -> policy.targetAppPackage?.split(".")?.lastOrNull() ?: "投屏软件"
            "hdmi" -> "HDMI ${policy.targetHdmiPort}"
            else -> "未设置"
        }
        statusText.text = policyName

        // 更新模式指示器
        val modeIndicator = findViewById<TextView>(R.id.modeIndicator)
        when (policy.mode) {
            "app" -> {
                modeIndicator.text = "APP模式"
                modeIndicator.setTextColor(getColor(android.R.color.holo_green_light))
            }
            "hdmi" -> {
                modeIndicator.text = "HDMI模式"
                modeIndicator.setTextColor(getColor(android.R.color.holo_orange_light))
            }
            else -> {
                modeIndicator.text = "未设置"
                modeIndicator.setTextColor(getColor(android.R.color.darker_gray))
            }
        }

        // 更新策略运行状态（显示暂停/运行中）
        val policyStatusIndicator = findViewById<TextView>(R.id.policyStatusIndicator)
        val executeBtnSubtitle = findViewById<TextView>(R.id.executeBtnSubtitle)
        if (isPaused) {
            policyStatusIndicator.text = "已暂停"
            policyStatusIndicator.setTextColor(getColor(android.R.color.holo_orange_light))
            executeBtnSubtitle.text = "策略已暂停，点击启动一次"
        } else if (isPolicyValid(policy)) {
            policyStatusIndicator.text = "运行中"
            policyStatusIndicator.setTextColor(getColor(android.R.color.holo_green_light))
            executeBtnSubtitle.text = "点击立即执行策略"
        } else {
            policyStatusIndicator.text = "未配置"
            policyStatusIndicator.setTextColor(getColor(android.R.color.darker_gray))
            executeBtnSubtitle.text = "点击立即执行策略"
        }

        // 更新连接指示器
        val connectionIndicator = findViewById<TextView>(R.id.connectionIndicator)
        if (token != null) {
            connectionIndicator.text = "● 已连接"
            connectionIndicator.setTextColor(getColor(android.R.color.holo_blue_light))
        } else {
            connectionIndicator.text = "○ 未连接"
            connectionIndicator.setTextColor(getColor(android.R.color.darker_gray))
        }
    }
}
