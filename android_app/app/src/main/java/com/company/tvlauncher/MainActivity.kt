package com.company.tvlauncher

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.work.Constraints
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class MainActivity : AppCompatActivity() {
    private val ioExecutor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private var lastPolicyExecutionTime = 0L
    private val EXECUTION_COOLDOWN = 5000L // 5 seconds cooldown to prevent loops
    private var lastEscapeToastTime = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val policyStore = PolicyStore(this)
        refreshStatus(policyStore)

        findViewById<Button>(R.id.openSettingsBtn).setOnClickListener {
            showPasswordDialog(policyStore)
        }
        findViewById<Button>(R.id.executeBtn).setOnClickListener {
            forceExecutePolicy(policyStore)
        }

        // Schedule periodic sync every 15 mins (minimum allowed by WorkManager)
        schedulePeriodicSync()
    }

    private fun forceExecutePolicy(policyStore: PolicyStore) {
        val policy = policyStore.getPolicy()
        
        // 检查策略是否有效
        if (!isPolicyValid(policy)) {
            showNoPolicyDialog()
            return
        }
        
        if (policy.mode == "app") {
            cleanupBackgroundApps(policy.targetAppPackage)
        }
        LauncherExecutor(this).execute(policy)
        lastPolicyExecutionTime = System.currentTimeMillis()
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
                } else {
                    Toast.makeText(this, "密码错误", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("取消", null)
            .show()
    }

    override fun onResume() {
        super.onResume()
        val policyStore = PolicyStore(this)
        refreshStatus(policyStore)
        
        // When returning to MainActivity (e.g. via Back or Home), 
        // check if we need to re-execute policy
        val now = System.currentTimeMillis()
        if (!policyStore.isEscapeModeActive() && now - lastPolicyExecutionTime > EXECUTION_COOLDOWN) {
            forceExecutePolicy(policyStore)
        } else if (policyStore.isEscapeModeActive() && now - lastEscapeToastTime > 5000) {
            lastEscapeToastTime = now
            Toast.makeText(this, "维护模式中（临时允许退出/更新），将自动恢复策略", Toast.LENGTH_LONG).show()
        }

        ioExecutor.execute {
            val net = NetworkInfoProvider(this).collect()
            val api = RemoteApi(this, policyStore)
            
            // Try online operations
            val registered = api.registerIfNeeded("MeetingTV", net)
            var heartbeatSuccess = api.heartbeat(net)
            if (!heartbeatSuccess) {
                policyStore.clearDeviceToken()
                api.registerIfNeeded("MeetingTV", net)
                heartbeatSuccess = api.heartbeat(net)
            }
            
            // Check for OTA update
            val updateInfo = api.checkUpdate()

            mainHandler.post {
                refreshStatus(policyStore)
                if (updateInfo != null) {
                    showUpdateDialog(updateInfo)
                }
            }
        }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            val policyStore = PolicyStore(this)
            if (policyStore.isEscapeModeActive() || !policyStore.getKioskEnabled()) {
                return super.onKeyDown(keyCode, event)
            }
            // User pressed back - cleanup and re-enforce policy
            forceExecutePolicy(policyStore)
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

    private fun refreshStatus(policyStore: PolicyStore) {
        val policy = policyStore.getPolicy()
        val token = policyStore.getDeviceToken()
        val tokenHint = if (token != null) "已注册" else "未注册(请在设置中配置后台地址)"
        findViewById<TextView>(R.id.statusText).text =
            "$tokenHint\n当前策略: ${policy.mode} / ${policy.targetAppPackage} / HDMI${policy.targetHdmiPort}"
    }
}
