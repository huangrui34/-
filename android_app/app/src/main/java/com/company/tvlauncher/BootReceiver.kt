package com.company.tvlauncher

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.util.Log

class BootReceiver : BroadcastReceiver() {
    companion object {
        private const val TAG = "BootReceiver"
    }

    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED ||
            intent?.action == "android.intent.action.QUICKBOOT_POWERON" ||
            intent?.action == Intent.ACTION_REBOOT) {

            Log.d(TAG, "接收到开机广播，立即启动TV Launcher")

            val serviceIntent = Intent(context, KeepAliveForegroundService::class.java)
            context.startService(serviceIntent)

            try {
                val policyStore = PolicyStore(context)
                val policy = policyStore.getPolicy()

                Log.d(TAG, "当前策略: ${policy.mode}")

                when (policy.mode) {
                    "hdmi" -> {
                        Log.d(TAG, "HDMI模式：直接启动HdmiActivity，HDMI${policy.targetHdmiPort}")
                        val hdmiIntent = Intent(context, HdmiActivity::class.java)
                        hdmiIntent.putExtra(HdmiActivity.EXTRA_HDMI_PORT, policy.targetHdmiPort)
                        hdmiIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        context.startActivity(hdmiIntent)
                    }
                    else -> {
                        Log.d(TAG, "APP模式：启动MainActivity，目标: ${policy.targetAppPackage}")
                        val launchIntent = Intent(context, MainActivity::class.java).apply {
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or
                                     Intent.FLAG_ACTIVITY_CLEAR_TOP or
                                     Intent.FLAG_ACTIVITY_SINGLE_TOP)
                        }
                        context.startActivity(launchIntent)

                        val handler = Handler(Looper.getMainLooper())
                        handler.postDelayed({
                            try {
                                val executor = LauncherExecutor(context)
                                Log.d(TAG, "APP模式：启动 ${policy.targetAppPackage}")
                                executor.launchApp(policy.targetAppPackage)
                            } catch (e: Exception) {
                                Log.e(TAG, "策略执行失败: ${e.message}")
                            }
                        }, 1500)
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "启动失败: ${e.message}")
            }
        }
    }
}
