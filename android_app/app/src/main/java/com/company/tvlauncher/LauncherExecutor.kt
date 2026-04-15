package com.company.tvlauncher

import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.widget.Toast

class LauncherExecutor(private val context: Context) {
    fun execute(policy: LaunchPolicy) {
        if (policy.mode == "app") {
            launchApp(policy.targetAppPackage)
        } else {
            switchHdmi(policy.targetHdmiPort)
        }
    }

    private fun launchApp(packageName: String) {
        val launchIntent = context.packageManager.getLaunchIntentForPackage(packageName)
        if (launchIntent != null) {
            launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(launchIntent)
        } else {
            Toast.makeText(context, "未找到目标APP: $packageName", Toast.LENGTH_SHORT).show()
        }
    }

    private fun switchHdmi(port: Int) {
        // 尝试多种HDMI切换方法
        val methods = listOf(
            { tryMethod1(port) },  // 小米电视系统方法1
            { tryMethod2(port) },  // 小米电视系统方法2
            { tryMethod3(port) },  // 通用电视方法1
            { tryMethod4(port) },  // 通用电视方法2
            { tryMethod5(port) },  // ADB命令方法
            { tryMethod6(port) }   // 最后回退方法
        )
        
        for ((index, method) in methods.withIndex()) {
            try {
                if (method()) {
                    Toast.makeText(context, "成功切换到 HDMI$port (方法${index + 1})", Toast.LENGTH_SHORT).show()
                    return
                }
            } catch (e: Exception) {
                // 继续尝试下一个方法
            }
        }
        
        // 所有方法都失败，打开设置页面
        val intent = Intent(Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        Toast.makeText(context, "无法自动切换：请在设置中选择 HDMI$port", Toast.LENGTH_LONG).show()
    }
    
    private fun tryMethod1(port: Int): Boolean {
        // 小米电视系统方法1：com.xiaomi.mitv.tvsystem
        val intent = Intent().apply {
            setClassName("com.xiaomi.mitv.tvsystem", "com.xiaomi.mitv.tvsystem.main.MainActivity")
            putExtra("source", "hdmi$port")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
        return true
    }
    
    private fun tryMethod2(port: Int): Boolean {
        // 小米电视系统方法2：com.xiaomi.mitv.settings
        val intent = Intent().apply {
            setClassName("com.xiaomi.mitv.settings", "com.xiaomi.mitv.settings.MainActivity")
            putExtra("action", "switch_source")
            putExtra("source", "hdmi$port")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
        return true
    }
    
    private fun tryMethod3(port: Int): Boolean {
        // 通用电视方法1：Android TV标准Intent
        val intent = Intent(Intent.ACTION_VIEW).apply {
            data = android.net.Uri.parse("content://android.media.tv/passthrough/com.mediatek.tvinput/.hdmi.HdmiInputService/HW$port")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
        return true
    }
    
    private fun tryMethod4(port: Int): Boolean {
        // 通用电视方法2：另一种TV输入服务
        val intent = Intent(Intent.ACTION_VIEW).apply {
            data = android.net.Uri.parse("content://android.media.tv/passthrough/.hdmi.HdmiInputService/HW$port")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
        return true
    }
    
    private fun tryMethod5(port: Int): Boolean {
        // ADB命令方法：通过shell命令切换
        try {
            val process = Runtime.getRuntime().exec(arrayOf("su", "-c", "am start -a android.intent.action.VIEW -d content://android.media.tv/passthrough/.hdmi.HdmiInputService/HW$port"))
            val exitCode = process.waitFor()
            return exitCode == 0
        } catch (e: Exception) {
            // 如果没有root权限，尝试普通shell
            try {
                val process = Runtime.getRuntime().exec(arrayOf("sh", "-c", "am start -a android.intent.action.VIEW -d content://android.media.tv/passthrough/.hdmi.HdmiInputService/HW$port"))
                val exitCode = process.waitFor()
                return exitCode == 0
            } catch (e2: Exception) {
                return false
            }
        }
    }
    
    private fun tryMethod6(port: Int): Boolean {
        // 最后回退方法：打开电视设置并发送按键事件
        try {
            // 打开电视设置
            val settingsIntent = Intent(Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(settingsIntent)
            
            // 等待设置打开
            Thread.sleep(1000)
            
            // 发送按键事件导航到HDMI设置（这需要root权限）
            try {
                Runtime.getRuntime().exec(arrayOf("su", "-c", "input keyevent KEYCODE_DPAD_RIGHT"))
                Thread.sleep(500)
                Runtime.getRuntime().exec(arrayOf("su", "-c", "input keyevent KEYCODE_ENTER"))
                return true
            } catch (e: Exception) {
                return false
            }
        } catch (e: Exception) {
            return false
        }
    }
}
