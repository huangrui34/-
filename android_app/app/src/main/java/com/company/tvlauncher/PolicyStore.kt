package com.company.tvlauncher

import android.content.Context

data class LaunchPolicy(
    val mode: String = "app",
    val targetAppPackage: String = "com.example.cast",
    val targetHdmiPort: Int = 1
)

class PolicyStore(private val context: Context) {
    private val prefs = context.getSharedPreferences("tv_policy", Context.MODE_PRIVATE)

    fun getServerBaseUrl(): String =
        prefs.getString("server_base_url", "http://localhost:8000") ?: "http://localhost:8000"

    fun setServerBaseUrl(url: String) {
        prefs.edit().putString("server_base_url", url.trimEnd('/')).apply()
    }

    fun getDeviceToken(): String? = prefs.getString("device_token", null)

    fun setDeviceToken(token: String) {
        prefs.edit().putString("device_token", token).apply()
    }

    fun clearDeviceToken() {
        prefs.edit().remove("device_token").apply()
    }

    fun getDeviceSn(): String =
        prefs.getString("device_sn", "") ?: ""

    fun setDeviceSn(sn: String) {
        prefs.edit().putString("device_sn", sn).apply()
    }

    fun getPolicy(): LaunchPolicy {
        return LaunchPolicy(
            mode = prefs.getString("mode", "app") ?: "app",
            targetAppPackage = prefs.getString("target_app_package", "com.example.cast")
                ?: "com.example.cast",
            targetHdmiPort = prefs.getInt("target_hdmi_port", 1)
        )
    }

    fun savePolicy(policy: LaunchPolicy) {
        prefs.edit()
            .putString("mode", policy.mode)
            .putString("target_app_package", policy.targetAppPackage)
            .putInt("target_hdmi_port", policy.targetHdmiPort)
            .apply()
    }

    fun getSettingsPassword(): String =
        prefs.getString("settings_password", "0000") ?: "0000"

    fun setSettingsPassword(password: String) {
        prefs.edit().putString("settings_password", password).apply()
    }

    fun getKioskEnabled(): Boolean = prefs.getBoolean("kiosk_enabled", true)

    fun setKioskEnabled(enabled: Boolean) {
        prefs.edit().putBoolean("kiosk_enabled", enabled).apply()
    }

    fun getEscapeUntilMs(): Long = prefs.getLong("escape_until_ms", 0L)

    fun setEscapeUntilMs(untilMs: Long) {
        prefs.edit().putLong("escape_until_ms", untilMs).apply()
    }

    fun isEscapeModeActive(nowMs: Long = System.currentTimeMillis()): Boolean {
        val until = getEscapeUntilMs()
        return until > nowMs
    }

    // 策略暂停状态
    fun isPolicyPaused(): Boolean = prefs.getBoolean("policy_paused", false)

    fun setPolicyPaused(paused: Boolean) {
        prefs.edit().putBoolean("policy_paused", paused).apply()
    }

    /**
     * 应用远程策略
     * @return true 如果策略有变化，false 如果策略没有变化
     */
    fun applyRemotePolicy(
        mode: String?,
        targetApp: String?,
        hdmiPort: Int?
    ): Boolean {
        if (mode.isNullOrBlank()) return false

        // 检查是否有变化
        val currentPolicy = getPolicy()
        val modeChanged = mode != currentPolicy.mode
        val appChanged = !targetApp.isNullOrBlank() && targetApp != currentPolicy.targetAppPackage
        val hdmiChanged = hdmiPort != null && hdmiPort > 0 && hdmiPort != currentPolicy.targetHdmiPort

        val hasChange = modeChanged || appChanged || hdmiChanged

        // 保存策略
        val editor = prefs.edit().putString("mode", mode)
        if (!targetApp.isNullOrBlank()) {
            editor.putString("target_app_package", targetApp)
        }
        if (hdmiPort != null && hdmiPort > 0) {
            editor.putInt("target_hdmi_port", hdmiPort)
        }
        editor.apply()

        return hasChange
    }
}
