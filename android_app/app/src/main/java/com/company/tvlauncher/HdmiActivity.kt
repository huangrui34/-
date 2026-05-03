package com.company.tvlauncher

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.tv.TvInputInfo
import android.media.tv.TvInputManager
import android.media.tv.TvView
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager

/**
 * HDMI输入显示Activity
 *
 * 使用Android TV Input Framework的TvView API直接显示HDMI输入信号。
 * 这是Android TV上切换到HDMI的正确方式，不依赖第三方APP。
 *
 * 支持多种芯片平台的HDMI输入：
 * - Amlogic/Droidlogic: com.droidlogic.tvinput/.services.Hdmi1InputService/HW5
 * - MediaTek: com.mediatek.tvinput/.hdmi.HDMIInputService/HW5
 * - MStar: com.mstar.tvinput/.service.Hdmi1InputService/HW5
 * - Realtek: com.realtek.tvinput/.services.Hdmi1InputService/HW5
 * - 其他: 通过遍历tvInputList自动发现
 *
 * 重要：TvView.tune()必须在Activity完全到前台后才能调用，
 * 否则会报错"don't tune source in background"并被丢弃。
 * 因此调谐操作延迟到onResume + 延迟 + onWindowFocusChanged中执行。
 */
class HdmiActivity : Activity() {

    companion object {
        private const val TAG = "HdmiActivity"
        const val EXTRA_HDMI_PORT = "hdmi_port"
        const val EXTRA_INPUT_ID = "input_id"
        private const val TUNE_DELAY_MS = 300L // 调谐延迟，等Activity完全到前台

        // 静态变量保存当前inputId，防止Activity被系统重建时丢失
        // （onSaveInstanceState在某些重建场景下不可靠）
        private var savedInputId: String? = null
    }

    private var tvView: TvView? = null
    private var tvInputManager: TvInputManager? = null
    private var currentInputId: String? = null
    private var hasTuned = false
    private var hasFocus = false
    private var isLeaving = false  // 标记正在离开，阻止延迟按键发送
    private val handler = Handler(Looper.getMainLooper())
    private var pendingTuneRunnable: Runnable? = null
    private var tuneTimeMs: Long = 0L  // 调谐时间，用于保护期判断
    private var targetPort: Int = 0    // 策略指定的HDMI端口号

    private val policyPauseReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == "com.company.tvlauncher.POLICY_PAUSED") {
                Log.d(TAG, "策略已暂停，阻止延迟按键并返回Launcher主页")
                isLeaving = true
                handler.removeCallbacksAndMessages(null)
                tvView?.reset()
                finish()
            }
        }
    }

    // 监听TV输入设备的添加/移除/状态变化，处理HDMI物理插拔和端口切换
    // 使用TvInputCallback而非BroadcastReceiver，因为android.intent.action.HDMI_PLUGGED
    // 在部分设备(Amlogic安卓6)上不可靠，而TvInputCallback是Android TV标准API
    private val tvInputCallback = object : TvInputManager.TvInputCallback() {
        override fun onInputAdded(inputId: String) {
            Log.d(TAG, "TV输入添加: $inputId, targetPort=$targetPort, currentInputId=$currentInputId")
            if (isLeaving) return
            val resolved = findInputIdForPort(targetPort)
            if (resolved != null && resolved != currentInputId) {
                Log.d(TAG, "HDMI输入变更: $currentInputId -> $resolved")
                currentInputId = resolved
                savedInputId = resolved
            }
            if (!hasTuned && currentInputId != null) {
                Log.d(TAG, "HDMI输入添加，调度调谐")
                scheduleTune()
            }
        }

        override fun onInputRemoved(inputId: String) {
            Log.d(TAG, "TV输入移除: $inputId, currentInputId=$currentInputId")
            if (inputId == currentInputId) {
                Log.d(TAG, "当前HDMI输入被移除，重置调谐状态")
                hasTuned = false
                tvView?.reset()
                currentInputId = null
            }
        }

        override fun onInputStateChanged(inputId: String, state: Int) {
            // state=0: CONNECTED(信号可用), state=2: DISCONNECTED
            Log.d(TAG, "TV输入状态变更: $inputId, state=$state, hasTuned=$hasTuned")
            if (state != 0 || isLeaving) return

            val resolved = findInputIdForPort(targetPort)
            if (resolved != null) {
                currentInputId = resolved
                savedInputId = resolved
            }

            if (!hasTuned && currentInputId != null) {
                Log.d(TAG, "HDMI信号恢复(state=0)，执行调谐")
                scheduleTune()
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // 从深色Splash主题切换到完整主题（防止冷启动白屏）
        setTheme(R.style.Theme_TvLauncher_Fullscreen)
        super.onCreate(savedInstanceState)
        Log.d(TAG, "========== HdmiActivity onCreate ==========")

        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        tvInputManager = getSystemService(TV_INPUT_SERVICE) as? TvInputManager
        if (tvInputManager == null) {
            Log.e(TAG, "TvInputManager不可用，无法切换HDMI")
            finish()
            return
        }

        listTvInputs()
        targetPort = intent?.getIntExtra(EXTRA_HDMI_PORT, 1) ?: 1

        // 优先从intent获取inputId（新的切换请求）
        // 只有intent没有指定时才从静态变量恢复（Activity重建场景）
        val intentInputId = resolveInputId()
        if (intentInputId != null) {
            currentInputId = intentInputId
            savedInputId = intentInputId
            Log.d(TAG, "从intent获取inputId: $currentInputId")
        } else if (!savedInputId.isNullOrBlank()) {
            currentInputId = savedInputId
            Log.d(TAG, "从静态变量恢复inputId: $currentInputId")
        } else if (savedInstanceState != null) {
            val restored = savedInstanceState.getString("current_input_id")
            if (!restored.isNullOrBlank()) {
                currentInputId = restored
                Log.d(TAG, "从savedInstanceState恢复inputId: $currentInputId")
            }
        }

        if (currentInputId.isNullOrBlank()) {
            Log.e(TAG, "无法确定HDMI输入ID")
            finish()
            return
        }
        Log.d(TAG, "目标HDMI输入ID: $currentInputId")

        tvView = TvView(this)
        tvView!!.setOnUnhandledInputEventListener { event ->
            Log.d(TAG, "TvView未处理的事件: $event")
            false
        }

        setContentView(tvView)

        tvView!!.systemUiVisibility = (View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_FULLSCREEN
                or View.SYSTEM_UI_FLAG_IMMERSIVE)

        // 注意：不在onCreate中调谐！TvView在Activity后台时调谐会被拒绝
        // 调谐将在onResume中延迟执行

        registerReceiver(policyPauseReceiver, IntentFilter("com.company.tvlauncher.POLICY_PAUSED"))
        tvInputManager?.registerCallback(tvInputCallback, handler)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        val newPort = intent?.getIntExtra(EXTRA_HDMI_PORT, 0) ?: 0
        if (newPort > 0) targetPort = newPort
        val currentPort = currentInputId?.let {
            // 从inputId中提取端口号，如HW5=1, HW6=2
            val hwMatch = Regex("""/HW(\d+)""").find(it)
            hwMatch?.groupValues?.get(1)?.toIntOrNull()?.let { hw -> hw - 4 }
        } ?: 0

        // 用端口号判断策略是否变化，不用inputId（因为TV可能只有一个HDMI输入）
        isLeaving = false  // 重置，允许调谐
        if (newPort > 0 && newPort != currentPort) {
            val newInputId = resolveInputId()
            if (newInputId != null) {
                currentInputId = newInputId
                savedInputId = newInputId
            }
            hasTuned = false
            Log.d(TAG, "onNewIntent - 端口变更: HDMI$currentPort -> HDMI$newPort, 需要重新调谐")
            scheduleTune()
        } else {
            Log.d(TAG, "onNewIntent - 端口未变化(HDMI$newPort), 跳过重新调谐")
        }
    }

    override fun onResume() {
        super.onResume()
        // 设置HDMI前台标志，供MainActivity判断是否需要重复启动
        getSharedPreferences("tv_policy", Context.MODE_PRIVATE)
            .edit().putBoolean("hdmi_foreground", true).apply()
        Log.d(TAG, "onResume - 当前输入: $currentInputId, hasTuned=$hasTuned, hasFocus=$hasFocus")

        // 延迟调谐，确保Activity完全到前台
        scheduleTune()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        this.hasFocus = hasFocus
        Log.d(TAG, "onWindowFocusChanged: hasFocus=$hasFocus, hasTuned=$hasTuned")

        if (hasFocus && !hasTuned && currentInputId != null) {
            // Activity获得焦点且尚未调谐，立即调谐
            Log.d(TAG, "窗口获得焦点，立即执行调谐")
            scheduleTune(delayMs = 100)
        }
    }

    override fun onPause() {
        super.onPause()
        Log.d(TAG, "onPause - 标记离开，取消待发送按键事件")
        isLeaving = true
        hasTuned = false
        getSharedPreferences("tv_policy", Context.MODE_PRIVATE)
            .edit().putBoolean("hdmi_foreground", false).apply()
        handler.removeCallbacksAndMessages(null)
        tvView?.reset()
    }

    override fun onSaveInstanceState(outState: android.os.Bundle) {
        super.onSaveInstanceState(outState)
        // 保存inputId，防止Activity被系统重建时丢失
        currentInputId?.let { outState.putString("current_input_id", it) }
        Log.d(TAG, "onSaveInstanceState: saved inputId=$currentInputId")
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.d(TAG, "onDestroy - 释放HDMI资源")
        try { unregisterReceiver(policyPauseReceiver) } catch (_: Exception) {}
        tvInputManager?.unregisterCallback(tvInputCallback)
        pendingTuneRunnable?.let { handler.removeCallbacks(it) }
        handler.removeCallbacksAndMessages(null)
        tvView?.reset()
        tvView = null
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        Log.d(TAG, "onKeyDown: keyCode=$keyCode")
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            // 调谐后5秒内的BACK键忽略，防止自动确认弹窗流程中的BACK键误退出
            val timeSinceTune = System.currentTimeMillis() - tuneTimeMs
            if (timeSinceTune < 5000) {
                Log.d(TAG, "调谐保护期内(${timeSinceTune}ms)，忽略BACK键")
                return true
            }
            Log.d(TAG, "BACK键按下，退出HDMI模式")
            tvView?.reset()
            finish()
            return true
        }
        // 调谐后5秒内的DPAD按键不拦截，让系统弹窗（如"输入源已接入"）能接收到
        val timeSinceTune = System.currentTimeMillis() - tuneTimeMs
        if (timeSinceTune < 5000 && (keyCode == KeyEvent.KEYCODE_DPAD_CENTER ||
                    keyCode == KeyEvent.KEYCODE_DPAD_RIGHT || keyCode == KeyEvent.KEYCODE_DPAD_LEFT ||
                    keyCode == KeyEvent.KEYCODE_DPAD_UP || keyCode == KeyEvent.KEYCODE_ENTER)) {
            Log.d(TAG, "调谐保护期内(${timeSinceTune}ms)，DPAD键穿透到系统弹窗")
            return false
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onKeyUp(keyCode: Int, event: KeyEvent?): Boolean {
        // 对应onKeyDown中的DPAD穿透逻辑
        val timeSinceTune = System.currentTimeMillis() - tuneTimeMs
        if (timeSinceTune < 5000 && (keyCode == KeyEvent.KEYCODE_DPAD_CENTER ||
                    keyCode == KeyEvent.KEYCODE_DPAD_RIGHT || keyCode == KeyEvent.KEYCODE_DPAD_LEFT ||
                    keyCode == KeyEvent.KEYCODE_DPAD_UP || keyCode == KeyEvent.KEYCODE_ENTER)) {
            return false
        }
        return super.onKeyUp(keyCode, event)
    }

    /**
     * 调度延迟调谐
     * TvView.tune()必须在Activity完全到前台后才能调用，
     * 否则会报"don't tune source in background"错误
     */
    private fun scheduleTune(delayMs: Long = TUNE_DELAY_MS) {
        if (hasTuned || currentInputId == null) return

        // 取消之前的调度
        pendingTuneRunnable?.let { handler.removeCallbacks(it) }

        pendingTuneRunnable = Runnable {
            if (!hasTuned && currentInputId != null) {
                Log.d(TAG, "延迟调谐执行 - hasFocus=$hasFocus")
                tuneToInput(currentInputId!!)
            }
        }
        handler.postDelayed(pendingTuneRunnable!!, delayMs)
    }

    private fun resolveInputId(): String? {
        val explicitInputId = intent?.getStringExtra(EXTRA_INPUT_ID)
        if (!explicitInputId.isNullOrBlank()) {
            Log.d(TAG, "使用显式指定的input_id: $explicitInputId")
            return explicitInputId
        }

        val port = intent?.getIntExtra(EXTRA_HDMI_PORT, 1) ?: 1
        Log.d(TAG, "根据HDMI端口$port 查找input ID")
        return findInputIdForPort(port)
    }

    /**
     * 根据HDMI端口号查找对应的TvInput ID
     *
     * 支持多种芯片平台：
     * - Amlogic/Droidlogic: 每个端口有独立的InputService
     * - MediaTek: 所有端口共用一个HDMIInputService，通过HW编号区分
     * - 未知平台: 遍历tvInputList按类型和编号自动匹配
     */
    private fun findInputIdForPort(port: Int): String? {
        val inputManager = tvInputManager ?: return null
        val inputList = inputManager.tvInputList

        // 已知的HDMI Input ID构造规则
        val knownInputIds = listOfNotNull(
            // Amlogic/Droidlogic (小米电视安卓6/9/11常用)
            when (port) {
                1 -> "com.droidlogic.tvinput/.services.Hdmi1InputService/HW5"
                2 -> "com.droidlogic.tvinput/.services.Hdmi2InputService/HW6"
                3 -> "com.droidlogic.tvinput/.services.Hdmi3InputService/HW7"
                4 -> "com.droidlogic.tvinput/.services.Hdmi4InputService/HW8"
                else -> null
            },
            // MediaTek (部分小米电视安卓9/11/13使用)
            when (port) {
                1 -> "com.mediatek.tvinput/.hdmi.HDMIInputService/HW5"
                2 -> "com.mediatek.tvinput/.hdmi.HDMIInputService/HW6"
                3 -> "com.mediatek.tvinput/.hdmi.HDMIInputService/HW7"
                4 -> "com.mediatek.tvinput/.hdmi.HDMIInputService/HW8"
                else -> null
            },
            // MStar/晨星 (小米电视2/3/3S/4早期型号, 安卓5/6)
            when (port) {
                1 -> "com.mstar.tvinput/.service.Hdmi1InputService/HW5"
                2 -> "com.mstar.tvinput/.service.Hdmi2InputService/HW6"
                3 -> "com.mstar.tvinput/.service.Hdmi3InputService/HW7"
                4 -> "com.mstar.tvinput/.service.Hdmi4InputService/HW8"
                else -> null
            },
            // Realtek/瑞昱 (部分红米电视低配型号, 安卓9)
            when (port) {
                1 -> "com.realtek.tvinput/.services.Hdmi1InputService/HW5"
                2 -> "com.realtek.tvinput/.services.Hdmi2InputService/HW6"
                3 -> "com.realtek.tvinput/.services.Hdmi3InputService/HW7"
                4 -> "com.realtek.tvinput/.services.Hdmi4InputService/HW8"
                else -> null
            }
        )

        // 1. 在已注册的输入列表中匹配已知ID
        for (candidateId in knownInputIds) {
            for (info in inputList) {
                if (info.id == candidateId) {
                    Log.d(TAG, "在tvInputList中找到HDMI$port 输入: ${info.id}")
                    return info.id
                }
            }
        }

        // 2. 按HW编号匹配（HW5=端口1, HW6=端口2, HW7=端口3, HW8=端口4）
        val hwNumber = port + 4
        for (info in inputList) {
            if (info.type == TvInputInfo.TYPE_HDMI && info.id.endsWith("/HW$hwNumber")) {
                Log.d(TAG, "通过HW编号匹配找到HDMI$port 输入: ${info.id}")
                return info.id
            }
        }

        // 3. 按名称模糊匹配
        for (info in inputList) {
            if (info.type == TvInputInfo.TYPE_HDMI) {
                val id = info.id.lowercase()
                if (id.contains("hdmi${port}") || id.contains("hdmi_${port}")) {
                    Log.d(TAG, "通过名称模糊匹配找到HDMI$port 输入: ${info.id}")
                    return info.id
                }
            }
        }

        // 4. 如果只有一个HDMI输入，直接使用
        val hdmiInputs = inputList.filter { it.type == TvInputInfo.TYPE_HDMI }
        if (hdmiInputs.size == 1) {
            Log.d(TAG, "只有一个HDMI输入，直接使用: ${hdmiInputs[0].id}")
            return hdmiInputs[0].id
        }

        // 5. 即使不在列表中，也返回构造的ID尝试调谐
        if (knownInputIds.isNotEmpty()) {
            Log.d(TAG, "HDMI$port 的ID(${knownInputIds[0]})不在tvInputList中，但仍尝试调谐")
            return knownInputIds[0]
        }

        Log.e(TAG, "未找到HDMI$port 输入，所有可用输入:")
        for (info in inputList) {
            Log.e(TAG, "  - ${info.id} (type=${info.type})")
        }

        return null
    }

    private fun listTvInputs() {
        val inputManager = tvInputManager ?: return
        val inputList = inputManager.tvInputList
        Log.d(TAG, "===== 已注册的TV输入设备 (${inputList.size}个) =====")
        for (info in inputList) {
            val typeStr = when (info.type) {
                TvInputInfo.TYPE_TUNER -> "TUNER"
                TvInputInfo.TYPE_COMPOSITE -> "COMPOSITE"
                TvInputInfo.TYPE_SVIDEO -> "SVIDEO"
                TvInputInfo.TYPE_SCART -> "SCART"
                TvInputInfo.TYPE_COMPONENT -> "COMPONENT"
                TvInputInfo.TYPE_VGA -> "VGA"
                TvInputInfo.TYPE_DVI -> "DVI"
                TvInputInfo.TYPE_HDMI -> "HDMI"
                TvInputInfo.TYPE_DISPLAY_PORT -> "DISPLAY_PORT"
                else -> "OTHER(${info.type})"
            }
            Log.d(TAG, "  ID: ${info.id}")
            Log.d(TAG, "  Type: $typeStr")
            Log.d(TAG, "  Label: ${info.loadLabel(this)}")
            Log.d(TAG, "  ---")
        }
    }

    private fun tuneToInput(inputId: String) {
        try {
            Log.d(TAG, "调谐到HDMI输入: $inputId")
            tvView?.tune(inputId, Uri.EMPTY)
            hasTuned = true
            tuneTimeMs = System.currentTimeMillis()
            Log.d(TAG, "HDMI调谐命令已发送")

            // 调谐后自动确认HDMI信号弹窗
            // 小米电视/Amlogic等平台调谐时会弹出"输入源已接入"提示，
            // 需要按确认键才能进入HDMI画面。延迟发送确认键自动关闭弹窗。
            scheduleConfirmDialog()
        } catch (e: Exception) {
            Log.e(TAG, "HDMI调谐失败: ${e.message}", e)
            fallbackSwitch(inputId)
        }
    }

    /**
     * 自动确认HDMI信号检测弹窗
     *
     * 小米电视（Amlogic/MediaTek芯片）在TvView.tune()后，
     * 系统会弹出"输入源已接入"提示，需要点击"查看"才能进入HDMI画面。
     *
     * 策略：调谐后直接定时发送确认键，不依赖焦点变化。
     * Amlogic安卓6上弹窗出现时Activity不会失去焦点，
     * 因此不能用焦点丢失来检测弹窗，改为直接定时发键。
     *
     * 步骤：
     * 1. 调谐后1秒发送 DPAD_CENTER 确认"查看"弹窗
     * 2. 再0.5秒后发送 DPAD_RIGHT + DPAD_CENTER 关闭残留的"输入源已接入"通知
     */
    private fun scheduleConfirmDialog() {
        // 第1步：1秒后发送确认键
        handler.postDelayed({
            if (isLeaving || !hasFocus) {
                Log.d(TAG, "已离开或失去焦点，跳过确认键 (isLeaving=$isLeaving, hasFocus=$hasFocus)")
                return@postDelayed
            }
            try {
                Log.d(TAG, "发送DPAD_CENTER确认HDMI弹窗")
                Runtime.getRuntime().exec(arrayOf("input", "keyevent", "KEYCODE_DPAD_CENTER"))
            } catch (e: Exception) {
                Log.w(TAG, "发送确认键失败: ${e.message}")
            }

            // 第2步：确认后0.5秒，发送RIGHT+CENTER关闭残留通知
            handler.postDelayed({
                if (isLeaving || !hasFocus) {
                    Log.d(TAG, "已离开或失去焦点，跳过关闭通知按键 (isLeaving=$isLeaving, hasFocus=$hasFocus)")
                    return@postDelayed
                }
                try {
                    Log.d(TAG, "发送DPAD_RIGHT+DPAD_CENTER关闭残留通知")
                    Runtime.getRuntime().exec(arrayOf("input", "keyevent", "KEYCODE_DPAD_RIGHT"))
                    Thread.sleep(300)
                    Runtime.getRuntime().exec(arrayOf("input", "keyevent", "KEYCODE_DPAD_CENTER"))
                } catch (e: Exception) {
                    Log.w(TAG, "发送关闭通知按键失败: ${e.message}")
                }
            }, 500L)
        }, 1000L)
    }

    private fun fallbackSwitch(inputId: String) {
        Log.d(TAG, "尝试备用HDMI切换方法")

        try {
            val intent = android.content.Intent("android.media.tv.action.SETUP_INPUTS")
            intent.putExtra("from_tv_source", true)
            intent.putExtra("android.media.tv.extra.INPUT_ID", inputId)
            intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(intent)
            Log.d(TAG, "备用方法1: SETUP_INPUTS已发送")
            finish()
            return
        } catch (e: Exception) {
            Log.w(TAG, "备用方法1失败: ${e.message}")
        }

        try {
            val intent = android.content.Intent("com.xiaomi.mitv.tvplayer.EXTSRC_PLAY")
            intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(intent)
            Log.d(TAG, "备用方法2: EXTSRC_PLAY已发送")
            finish()
            return
        } catch (e: Exception) {
            Log.w(TAG, "备用方法2失败: ${e.message}")
        }

        try {
            val intent = packageManager.getLaunchIntentForPackage(LauncherExecutor.HDMI_TV_PLAYER_PACKAGE)
            if (intent != null) {
                intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
                startActivity(intent)
                Log.d(TAG, "备用方法3: tvplayer已启动")
                finish()
                return
            }
        } catch (e: Exception) {
            Log.w(TAG, "备用方法3失败: ${e.message}")
        }

        Log.e(TAG, "所有HDMI切换方法均失败")
    }
}
