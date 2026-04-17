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

/**
 * 前台服务，用于防止APP被系统清理
 * 同时持续监控目标APP是否在运行
 *
 * 策略保活逻辑：
 * - APP模式：确保目标APP一直在前台运行
 * - HDMI模式：确保com.xiaomi.mitv.tvplayer一直在运行
 */
class KeepAliveForegroundService : Service() {

    companion object {
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "tv_launcher_keep_alive"
        private const val TAG = "KeepAliveService"
        private const val CHECK_INTERVAL_MS = 5000L // 5秒检查一次
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
        // 确保服务持续运行，被杀死后自动重启
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        keepAliveRunnable?.let { handler.removeCallbacks(it) }
        // 服务被销毁时，尝试重启自己
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
        val statusText = when (policy.mode) {
            "app" -> "保活: ${policy.targetAppPackage}"
            "hdmi" -> "保活: 小米电视播放器 (HDMI${policy.targetHdmiPort})"
            else -> "策略保活服务运行中"
        }

        // 点击通知打开MainActivity
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("TV Launcher 策略保活")
            .setContentText(statusText)
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    /**
     * 更新通知显示当前保活状态
     */
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
                    val policy = policyStore.getPolicy()

                    when (policy.mode) {
                        "app" -> {
                            // APP模式：确保目标APP在运行
                            val targetPackage = policy.targetAppPackage
                            if (!targetPackage.isNullOrBlank() &&
                                targetPackage != "com.example.cast" &&
                                targetPackage != "com.android.settings") {

                                if (!executor.isAppRunning(targetPackage)) {
                                    // 目标APP不在运行，重新启动
                                    android.util.Log.d(TAG, "目标APP未运行，重新启动: $targetPackage")
                                    executor.launchApp(targetPackage)
                                    lastLaunchedPackage = targetPackage
                                    consecutiveFailures++

                                    // 更新通知
                                    updateNotification()
                                } else {
                                    consecutiveFailures = 0
                                }
                            }
                        }
                        "hdmi" -> {
                            // HDMI模式：确保小米电视播放器在运行
                            if (!executor.isAppRunning(HDMI_PLAYER_PACKAGE)) {
                                android.util.Log.d(TAG, "小米电视播放器未运行，重新启动")
                                // 启动小米电视播放器
                                executor.launchApp(HDMI_PLAYER_PACKAGE)
                                lastLaunchedPackage = HDMI_PLAYER_PACKAGE
                                consecutiveFailures++

                                // 等待播放器启动后再执行HDMI切换
                                handler.postDelayed({
                                    if (executor.isAppRunning(HDMI_PLAYER_PACKAGE)) {
                                        executor.execute(policy)
                                    }
                                }, 2000)

                                // 更新通知
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

                // 每5秒检查一次
                handler.postDelayed(this, CHECK_INTERVAL_MS)
            }
        }

        // 延迟1秒后开始检查（加快首次检查）
        handler.postDelayed(keepAliveRunnable!!, 1000)
    }
}
