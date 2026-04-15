package com.company.tvlauncher

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.widget.Toast

class HomeKeyService : AccessibilityService() {
    private var lastHomeDownAtMs: Long = 0L
    private var homeDownCount: Int = 0

    override fun onServiceConnected() {
        val info = serviceInfo ?: AccessibilityServiceInfo()
        info.flags = info.flags or AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
        serviceInfo = info
    }

    override fun onKeyEvent(event: KeyEvent): Boolean {
        val store = PolicyStore(applicationContext)
        if (!store.getKioskEnabled()) return super.onKeyEvent(event)

        val now = System.currentTimeMillis()
        val escapeActive = store.isEscapeModeActive(now)
        if (escapeActive) return super.onKeyEvent(event)

        if (event.action == KeyEvent.ACTION_DOWN && event.keyCode == KeyEvent.KEYCODE_HOME) {
            val withinWindow = now - lastHomeDownAtMs <= 2500
            homeDownCount = if (withinWindow) homeDownCount + 1 else 1
            lastHomeDownAtMs = now

            if (homeDownCount >= 6) {
                homeDownCount = 0
                store.setEscapeUntilMs(now + 10 * 60 * 1000L)
                Handler(Looper.getMainLooper()).post {
                    Toast.makeText(this, "已进入维护模式（10分钟）", Toast.LENGTH_LONG).show()
                }
                performGlobalAction(GLOBAL_ACTION_HOME)
                startSystemLauncherIfPossible()
            }
            return true
        }

        if (event.keyCode == KeyEvent.KEYCODE_HOME || event.keyCode == KeyEvent.KEYCODE_BACK) {
            return true
        }

        return super.onKeyEvent(event)
    }

    private fun startSystemLauncherIfPossible() {
        val pm = packageManager
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)
        val candidates = pm.queryIntentActivities(intent, PackageManager.MATCH_DEFAULT_ONLY)
            .mapNotNull { it.activityInfo }
            .filter { it.packageName != packageName }

        val target = candidates.firstOrNull() ?: return
        val launch = Intent(Intent.ACTION_MAIN)
            .addCategory(Intent.CATEGORY_HOME)
            .setComponent(ComponentName(target.packageName, target.name))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            startActivity(launch)
        } catch (_: Exception) {
        }
    }

    override fun onAccessibilityEvent(event: android.view.accessibility.AccessibilityEvent?) {}

    override fun onInterrupt() {}
}
