package com.company.tvlauncher

import android.content.Context

data class LaunchPolicy(
    val mode: String = "app",
    val targetAppPackage: String = "com.example.cast",
    val targetHdmiPort: Int = 1
)

class PolicyStore(private val context: Context) {
    private val prefs = context.getSharedPreferences("tv_policy", Context.MODE_PRIVATE)

    fun getServerBaseUrl(): String {
        // 优先使用SharedPreferences中的URL
        val saved = prefs.getString("server_base_url", null)
        if (!saved.isNullOrBlank() && saved != "http://localhost:8000") {
            return saved!!
        }
        // 如果没有保存的URL，尝试从全局Settings中读取（由deploy-tv设置）
        try {
            val globalUrl = android.provider.Settings.Global.getString(
                context.contentResolver,
                "tv_launcher_server_url"
            )
            if (!globalUrl.isNullOrBlank()) {
                // 保存到SharedPreferences，以后不再读取全局设置
                prefs.edit().putString("server_base_url", globalUrl.trimEnd('/')).apply()
                return globalUrl.trimEnd('/')
            }
        } catch (e: Exception) {
            // 忽略
        }
        return "http://localhost:8000"
    }

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

    // HDMI自动切换：保存HDMI接入前的策略
    fun savePreHdmiPolicy(policy: LaunchPolicy) {
        prefs.edit()
            .putString("pre_hdmi_policy_mode", policy.mode)
            .putString("pre_hdmi_policy_app", policy.targetAppPackage)
            .putInt("pre_hdmi_policy_hdmiport", policy.targetHdmiPort)
            .apply()
    }

    fun getPreHdmiPolicy(): LaunchPolicy? {
        val mode = prefs.getString("pre_hdmi_policy_mode", null) ?: return null
        return LaunchPolicy(
            mode = mode,
            targetAppPackage = prefs.getString("pre_hdmi_policy_app", "com.example.cast")
                ?: "com.example.cast",
            targetHdmiPort = prefs.getInt("pre_hdmi_policy_hdmiport", 1)
        )
    }

    fun clearPreHdmiPolicy() {
        prefs.edit()
            .remove("pre_hdmi_policy_mode")
            .remove("pre_hdmi_policy_app")
            .remove("pre_hdmi_policy_hdmiport")
            .apply()
    }

    // HDMI自动切换标记：当前是否因HDMI接入而自动切换了策略
    fun isHdmiAutoSwitched(): Boolean = prefs.getBoolean("hdmi_auto_switched", false)

    fun setHdmiAutoSwitched(value: Boolean) {
        prefs.edit().putBoolean("hdmi_auto_switched", value).apply()
    }

    // HDMI自动切换功能开关（用户可关闭）
    fun isHdmiAutoSwitchEnabled(): Boolean = prefs.getBoolean("hdmi_auto_switch_enabled", true)

    fun setHdmiAutoSwitchEnabled(enabled: Boolean) {
        prefs.edit().putBoolean("hdmi_auto_switch_enabled", enabled).apply()
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
