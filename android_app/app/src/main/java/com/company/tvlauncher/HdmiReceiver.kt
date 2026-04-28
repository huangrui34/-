package com.company.tvlauncher

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * HDMI热插拔广播接收器
 *
 * 监听系统的 HDMI_PLUGGED 广播，当HDMI信号接入/断开时：
 * - HDMI接入 → 通知MainActivity切换到HDMI1策略
 * - HDMI断开 → 通知MainActivity恢复之前的策略
 *
 * 小米电视(Android 6/9)均支持 android.intent.action.HDMI_PLUGGED 系统广播
 */
class HdmiReceiver : BroadcastReceiver() {

    companion object {
        const val ACTION_HDMI_STATUS_CHANGED = "com.company.tvlauncher.HDMI_STATUS_CHANGED"
        const val EXTRA_HDMI_CONNECTED = "hdmi_connected"
    }

    override fun onReceive(context: Context?, intent: Intent?) {
        if (context == null || intent == null) return

        when (intent.action) {
            Intent.ACTION_HEADSET_PLUG -> {
                // 某些设备用此action，不处理
            }
            "android.intent.action.HDMI_PLUGGED" -> {
                val connected = intent.getBooleanExtra("state", false)
                android.util.Log.d("HdmiReceiver", "HDMI状态变化: connected=$connected")

                // 转发为本地广播，让MainActivity处理
                val localIntent = Intent(ACTION_HDMI_STATUS_CHANGED)
                localIntent.putExtra(EXTRA_HDMI_CONNECTED, connected)
                localIntent.setPackage(context.packageName)
                context.sendBroadcast(localIntent)
            }
        }
    }
}
