package com.company.tvlauncher

import android.app.ActivityManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.widget.Toast
import androidx.core.app.NotificationCompat

class KeepAliveForegroundService : Service() {

    companion object {
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "tv_launcher_keep_alive"
        private const val TAG = "KeepAliveService"
        private const val CHECK_INTERVAL_MS = 5000L
        private const val HDMI_PLAYER_PACKAGE = "com.xiaomi.mitv.tvplayer"
    }

    private val handler = Handler(Looper.getMainLooper())
    private var keepAliveRunnable: Runnable? = null
    private var lastLaunchedPackage: String? = null
    private var consecutiveFailures = 0

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, createNotification())
        startKeepAliveCheck()
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        keepAliveRunnable?.let { handler.removeCallbacks(it) }
        val restartIntent = Intent(applicationContext, KeepAliveForegroundService::class.java)
        applicationContext.startService(restartIntent)
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "TV Launcher 保活服务",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "保持TV Launcher在后台运行，确保策略APP持续运行"
                setShowBadge(false)
            }

            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(): Notification {
        val policyStore = PolicyStore(this)
        val policy = policyStore.getPolicy()
        val isPaused = policyStore.isPolicyPaused()
        val statusText = if (isPaused) {
            "策略已暂停"
        } else {
            val hdmiAutoSwitched = policyStore.isHdmiAutoSwitched()
            when (policy.mode) {
                "app" -> "保活: ${policy.targetAppPackage}"
                "hdmi" -> {
                    if (hdmiAutoSwitched) "HDMI自动切换中 (HDMI${policy.targetHdmiPort})"
                    else "保活: 小米电视播放器 (HDMI${policy.targetHdmiPort})"
                }
                else -> "策略保活服务运行中"
            }
        }

        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("TV Launcher ${if (isPaused) "(已暂停)" else "策略保活"}")
            .setContentText(statusText)
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    private fun updateNotification() {
        val notificationManager = getSystemService(NotificationManager::class.java)
        notificationManager.notify(NOTIFICATION_ID, createNotification())
    }

    private fun startKeepAliveCheck() {
        val executor = LauncherExecutor(this)
        val policyStore = PolicyStore(this)

        keepAliveRunnable = object : Runnable {
            override fun run() {
                try {
                    if (policyStore.isPolicyPaused()) {
                        // 策略暂停时：不强制拉回主页，让用户自由操作
                        // 只更新通知栏状态
                        updateNotification()
                        handler.postDelayed(this, CHECK_INTERVAL_MS)
                        return
                    }

                    val policy = policyStore.getPolicy()

                    when (policy.mode) {
                        "app" -> {
                            val targetPackage = policy.targetAppPackage
                            if (!targetPackage.isNullOrBlank() &&
                                targetPackage != "com.example.cast" &&
                                targetPackage != "com.android.settings") {

                                if (!executor.isAppRunning(targetPackage)) {
                                    android.util.Log.d(TAG, "目标APP未运行，重新启动: $targetPackage")
                                    executor.launchApp(targetPackage)
                                    lastLaunchedPackage = targetPackage
                                    consecutiveFailures++
                                    updateNotification()
                                } else {
                                    consecutiveFailures = 0
                                }
                            }
                        }
                        "hdmi" -> {
                            // HDMI模式：检查HdmiActivity是否在前台
                            val hdmiFg = getSharedPreferences("tv_policy", Context.MODE_PRIVATE)
                                .getBoolean("hdmi_foreground", false)
                            if (!hdmiFg) {
                                android.util.Log.d(TAG, "HdmiActivity不在前台，重新执行HDMI策略")
                                executor.execute(policy)
                                updateNotification()
                            } else {
                                consecutiveFailures = 0
                            }
                        }
                    }
                } catch (e: Exception) {
                    android.util.Log.e(TAG, "保活检查异常: ${e.message}")
                    e.printStackTrace()
                }

                handler.postDelayed(this, CHECK_INTERVAL_MS)
            }
        }

        handler.postDelayed(keepAliveRunnable!!, 1000)
    }

    /**
     * 检查我们自己的APP是否在前台（MainActivity/SettingsActivity/HdmiActivity等）
     * 策略暂停时，只有用户在第三方APP中才需要拉回主页，在我们自己的APP内不干预
     */
    private fun isOurAppInForeground(): Boolean {
        // 方法1：检查launcher_foreground标志（MainActivity设置）
        val prefs = getSharedPreferences("tv_policy", Context.MODE_PRIVATE)
        if (prefs.getBoolean("launcher_foreground", true)) return true

        // 方法2：通过getRunningTasks检查前台Activity是否属于我们的包
        return try {
            val am = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val tasks = am.getRunningTasks(1)
            if (tasks != null && tasks.isNotEmpty()) {
                tasks[0].topActivity?.packageName == packageName
            } else {
                false
            }
        } catch (e: Exception) {
            false
        }
    }
}
