package com.company.tvlauncher

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.util.Log

/**
 * 开机启动接收器
 * 电视开机后自动启动TV Launcher并执行策略
 */
class BootReceiver : BroadcastReceiver() {
    companion object {
        private const val TAG = "BootReceiver"
    }

    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED ||
            intent?.action == "android.intent.action.QUICKBOOT_POWERON") {

            Log.d(TAG, "接收到开机广播，准备启动TV Launcher")

            // 启动前台保活服务
            val serviceIntent = Intent(context, KeepAliveForegroundService::class.java)
            context.startService(serviceIntent)

            // For older/slow devices, give the system a bit more time to settle
            // but start the launcher as early as possible.
            val handler = Handler(Looper.getMainLooper())
            handler.postDelayed({
                try {
                    val policyStore = PolicyStore(context)
                    val policy = policyStore.getPolicy()

                    Log.d(TAG, "启动MainActivity，当前策略: ${policy.mode}")

                    val launchIntent = Intent(context, MainActivity::class.java).apply {
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or
                                 Intent.FLAG_ACTIVITY_CLEAR_TOP or
                                 Intent.FLAG_ACTIVITY_SINGLE_TOP)
                    }
                    context.startActivity(launchIntent)

                    // 执行策略
                    val executor = LauncherExecutor(context)

                    when (policy.mode) {
                        "app" -> {
                            // APP模式：直接启动目标APP
                            Log.d(TAG, "APP模式：启动 ${policy.targetAppPackage}")
                            executor.launchApp(policy.targetAppPackage)
                        }
                        "hdmi" -> {
                            // HDMI模式：确保小米电视播放器运行后切换HDMI
                            Log.d(TAG, "HDMI模式：启动小米电视播放器并切换到HDMI${policy.targetHdmiPort}")
                            executor.execute(policy)
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "启动失败: ${e.message}")
                }
            }, 3000) // 3秒后启动，给系统足够的启动时间
        }
    }
}
