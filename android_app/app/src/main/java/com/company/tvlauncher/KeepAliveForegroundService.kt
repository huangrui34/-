package com.company.tvlauncher

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
                        // 策略暂停时，确保Launcher在前台（不要停留在投屏APP中）
                        val prefs = getSharedPreferences("tv_policy", Context.MODE_PRIVATE)
                        val isLauncherFg = prefs.getBoolean("launcher_foreground", true)
                        if (!isLauncherFg) {
                            android.util.Log.d(TAG, "策略已暂停，Launcher不在前台，切回主页")
                            val intent = Intent(this@KeepAliveForegroundService, MainActivity::class.java)
                            intent.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
                            startActivity(intent)
                        }
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
                            consecutiveFailures = 0
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
}
