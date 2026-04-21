package com.company.tvlauncher

import android.content.Context
import android.os.Build
import android.os.Environment
import android.os.StatFs
import android.app.ActivityManager
import android.provider.Settings
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import java.io.File

class RemoteApi(
    private val context: Context,
    private val policyStore: PolicyStore
) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    private fun getRamUsage(): String {
        return try {
            val activityManager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val memoryInfo = ActivityManager.MemoryInfo()
            activityManager.getMemoryInfo(memoryInfo)
            val total = memoryInfo.totalMem / (1024 * 1024)
            val avail = memoryInfo.availMem / (1024 * 1024)
            val used = total - avail
            "$used MB / $total MB"
        } catch (_: Exception) { "N/A" }
    }

    private fun getStorageUsage(): String {
        return try {
            val path = Environment.getDataDirectory()
            val stat = StatFs(path.path)
            val blockSize = stat.blockSizeLong
            val totalBlocks = stat.blockCountLong
            val availBlocks = stat.availableBlocksLong
            val total = (totalBlocks * blockSize) / (1024 * 1024)
            val avail = (availBlocks * blockSize) / (1024 * 1024)
            val used = total - avail
            "$used MB / $total MB"
        } catch (_: Exception) { "N/A" }
    }

    private fun getInstalledAppsJson(): String {
        val pm = context.packageManager
        val apps = pm.getInstalledApplications(PackageManager.GET_META_DATA)
        val installedPackages = JSONArray()
        for (app in apps) {
            // Only report non-system apps or common TV apps to keep it clean
            val isSystemApp = (app.flags and ApplicationInfo.FLAG_SYSTEM) != 0
            if (!isSystemApp || app.packageName.contains("mitv") || app.packageName.contains("video")) {
                installedPackages.put(app.packageName)
            }
        }
        return installedPackages.toString()
    }

    fun registerIfNeeded(deviceName: String, network: TvNetworkInfo): Boolean {
        if (policyStore.getDeviceToken() != null) return true
        val sn = resolveSerial()
        policyStore.setDeviceSn(sn)
        val base = policyStore.getServerBaseUrl()
        
        // Auto-naming: Use MAC address if deviceName is generic or blank
        val finalName = if (deviceName == "MeetingTV" || deviceName.isBlank()) {
            val macTail = network.wifiMac.replace(":", "").takeLast(4).ifBlank { 
                network.ethMac.replace(":", "").takeLast(4) 
            }
            "TV-$macTail"
        } else {
            deviceName
        }

        val body = JSONObject()
            .put("device_sn", sn)
            .put("device_name", finalName)
            .put("model_name", Build.MODEL)
            .put("wifi_mac", network.wifiMac)
            .put("eth_mac", network.ethMac)
            .toString()
            .toRequestBody(jsonMedia)
        val req = Request.Builder()
            .url("$base/api/v1/devices/register")
            .post(body)
            .build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) return false
            val json = JSONObject(resp.body?.string() ?: return false)
            val token = json.optString("token", "")
            if (token.isNotBlank()) {
                policyStore.setDeviceToken(token)
                return true
            }
        }
        return false
    }

    fun heartbeat(network: TvNetworkInfo): Boolean {
        val token = policyStore.getDeviceToken() ?: return false
        val base = policyStore.getServerBaseUrl()
        val appsJson = getInstalledAppsJson()
        val body = JSONObject()
            .put("wifi_ip", network.wifiIp)
            .put("eth_ip", network.ethIp)
            .put("wifi_mac", network.wifiMac)
            .put("eth_mac", network.ethMac)
            .put("network_ssid", network.ssid)
            .put("installed_apps", appsJson)
            .put("ram_usage", getRamUsage())
            .put("storage_usage", getStorageUsage())
            .put("status", "ok")
            .toString()
            .toRequestBody(jsonMedia)
        val req = Request.Builder()
            .url("$base/api/v1/devices/heartbeat")
            .header("X-Device-Token", token)
            .post(body)
            .build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) return false
            val json = JSONObject(resp.body?.string() ?: return false)
            val policy = json.optJSONObject("policy") ?: return true
            val mode = policy.optString("mode", "")
            val app = policy.optString("target_app_package", "")
            val hdmi = if (policy.has("target_hdmi_port") && !policy.isNull("target_hdmi_port")) {
                policy.getInt("target_hdmi_port")
            } else {
                null
            }

            // 应用远程策略，返回是否发生变化
            val policyChanged = policyStore.applyRemotePolicy(
                mode = mode.ifBlank { null },
                targetApp = app.ifBlank { null },
                hdmiPort = hdmi
            )

            // 检查策略暂停状态
            val policyPaused = json.optBoolean("policy_paused", false)
            android.util.Log.d("RemoteApi", "心跳同步: policy_paused=$policyPaused")
            policyStore.setPolicyPaused(policyPaused)

            // 只有策略真正变化时才发送广播，避免重复执行
            if (policyChanged && mode.isNotBlank()) {
                android.util.Log.d("RemoteApi", "策略已变化，发送更新广播")
                val intent = android.content.Intent("com.company.tvlauncher.POLICY_UPDATED")
                context.sendBroadcast(intent)
            }

            return true
        }
    }

    fun checkUpdate(): JSONObject? {
        val base = policyStore.getServerBaseUrl()
        val version = context.packageManager.getPackageInfo(context.packageName, 0).versionName
        val req = Request.Builder()
            .url("$base/api/v1/ota/check?version=$version")
            .get()
            .build()
        try {
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return null
                val json = JSONObject(resp.body?.string() ?: return null)
                if (json.optBoolean("update_available", false)) {
                    return json
                }
            }
        } catch (_: Exception) {}
        return null
    }

    private fun resolveSerial(): String {
        val androidId = Settings.Secure.getString(
            context.contentResolver,
            Settings.Secure.ANDROID_ID
        )
        return androidId ?: "tv-${System.currentTimeMillis()}"
    }
}
