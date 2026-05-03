package com.company.tvlauncher

import android.content.Context
import android.net.wifi.WifiConfiguration
import android.net.wifi.WifiEnterpriseConfig
import android.net.wifi.WifiManager
import android.util.Log

data class WifiConfig(
    val ssid: String,
    val security: String,      // "open" | "wpa2_psk" | "wpa2_enterprise"
    val password: String? = null,
    val identity: String? = null,
    val hidden: Boolean = false
)

class WifiConfigManager(private val context: Context) {
    companion object {
        private const val TAG = "WifiConfigManager"
    }

    fun saveCurrentWifiState(): Int {
        val wifiManager = context.applicationContext
            .getSystemService(Context.WIFI_SERVICE) as WifiManager
        val currentNetId = wifiManager.connectionInfo?.networkId ?: -1
        Log.d(TAG, "Saved current WiFi state: networkId=$currentNetId")
        return currentNetId
    }

    fun connectToWifi(config: WifiConfig): Int {
        val wifiManager = context.applicationContext
            .getSystemService(Context.WIFI_SERVICE) as WifiManager

        if (!wifiManager.isWifiEnabled) {
            wifiManager.isWifiEnabled = true
            Thread.sleep(2000)
        }

        removeExistingConfig(wifiManager, config.ssid)

        val wifiConfig = when (config.security) {
            "open" -> createOpenConfig(config)
            "wpa2_psk" -> createWpa2PskConfig(config)
            "wpa2_enterprise" -> createEnterpriseConfig(config)
            else -> {
                Log.e(TAG, "Unknown security type: ${config.security}")
                return -1
            }
        }

        val netId = wifiManager.addNetwork(wifiConfig)
        if (netId == -1) {
            Log.e(TAG, "Failed to add network for SSID: ${config.ssid}")
            return -1
        }

        Log.d(TAG, "Added network: netId=$netId, SSID=${config.ssid}, security=${config.security}")
        wifiManager.disconnect()
        wifiManager.enableNetwork(netId, true)
        wifiManager.reconnect()
        Log.d(TAG, "WiFi reconnecting to SSID=${config.ssid}")
        return netId
    }

    fun revertToNetwork(previousNetId: Int) {
        if (previousNetId == -1) {
            Log.d(TAG, "No previous network to revert to")
            return
        }
        val wifiManager = context.applicationContext
            .getSystemService(Context.WIFI_SERVICE) as WifiManager
        wifiManager.disconnect()
        wifiManager.enableNetwork(previousNetId, true)
        wifiManager.reconnect()
        Log.d(TAG, "Reverted to previous network: netId=$previousNetId")
    }

    private fun removeExistingConfig(wifiManager: WifiManager, ssid: String) {
        val configuredNetworks = wifiManager.configuredNetworks ?: return
        val quotedSsid = "\"$ssid\""
        for (network in configuredNetworks) {
            if (network.SSID == quotedSsid) {
                wifiManager.removeNetwork(network.networkId)
                Log.d(TAG, "Removed existing config for SSID: $ssid")
            }
        }
    }

    private fun createOpenConfig(config: WifiConfig): WifiConfiguration {
        return WifiConfiguration().apply {
            SSID = "\"${config.ssid}\""
            status = WifiConfiguration.Status.ENABLED
            allowedKeyManagement.set(WifiConfiguration.KeyMgmt.NONE)
            hiddenSSID = config.hidden
        }
    }

    private fun createWpa2PskConfig(config: WifiConfig): WifiConfiguration {
        return WifiConfiguration().apply {
            SSID = "\"${config.ssid}\""
            status = WifiConfiguration.Status.ENABLED
            allowedKeyManagement.set(WifiConfiguration.KeyMgmt.WPA_PSK)
            preSharedKey = "\"${config.password}\""
            hiddenSSID = config.hidden
        }
    }

    private fun createEnterpriseConfig(config: WifiConfig): WifiConfiguration {
        val enterpriseConfig = WifiEnterpriseConfig().apply {
            setIdentity(config.identity ?: "")
            setPassword(config.password ?: "")
            eapMethod = WifiEnterpriseConfig.Eap.PEAP
            phase2Method = WifiEnterpriseConfig.Phase2.MSCHAPV2
        }

        return WifiConfiguration().apply {
            SSID = "\"${config.ssid}\""
            status = WifiConfiguration.Status.ENABLED
            allowedKeyManagement.set(WifiConfiguration.KeyMgmt.WPA_EAP)
            allowedKeyManagement.set(WifiConfiguration.KeyMgmt.IEEE8021X)
            this.enterpriseConfig = enterpriseConfig
            hiddenSSID = config.hidden
        }
    }
}
