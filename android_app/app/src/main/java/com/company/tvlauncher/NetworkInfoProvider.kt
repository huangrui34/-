package com.company.tvlauncher

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.text.format.Formatter
import java.net.Inet4Address
import java.net.NetworkInterface

data class TvNetworkInfo(
    val wifiMac: String,
    val ethMac: String,
    val ssid: String,
    val wifiIp: String,
    val ethIp: String,
    val networkType: String  // "wifi" | "ethernet" | "none"
)

class NetworkInfoProvider(private val context: Context) {
    fun collect(): TvNetworkInfo {
        val wifiManager =
            context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager

        val info = wifiManager.connectionInfo
        val ssidRaw = info?.ssid ?: ""
        val ssid = ssidRaw.replace("\"", "")

        // WiFi IP
        val wifiIp = if (info != null && info.ipAddress != 0) {
            Formatter.formatIpAddress(info.ipAddress)
        } else {
            val raw = ipv4FromInterface("wlan0")
            if (raw == "N/A") "0.0.0.0" else raw
        }

        // Ethernet IP
        val ethIpRaw = ipv4FromInterface("eth0")
        val ethIp = if (ethIpRaw == "N/A") "0.0.0.0" else ethIpRaw

        // Detect active network type via ConnectivityManager
        val networkType = detectActiveNetworkType()

        return TvNetworkInfo(
            wifiMac = getMacAddressByInterface("wlan0") ?: getMacAddressByInterface("p2p-wlan0-0") ?: "N/A",
            ethMac = getMacAddressByInterface("eth0") ?: "N/A",
            ssid = if (ssid == "<unknown ssid>" || ssid.isBlank()) "未连接" else ssid,
            wifiIp = wifiIp,
            ethIp = ethIp,
            networkType = networkType
        )
    }

    /**
     * 检测当前活动网络类型
     * 小米电视连接有线后WiFi通常不会自动断开，需要通过ConnectivityManager判断哪个是活动网络
     */
    private fun detectActiveNetworkType(): String {
        return try {
            val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val activeNetwork = cm.activeNetwork
            val caps = cm.getNetworkCapabilities(activeNetwork)
            when {
                caps == null -> "none"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
                else -> "none"
            }
        } catch (_: Exception) {
            // Fallback: 按IP判断
            val ethIp = ipv4FromInterface("eth0")
            val wifiIp = ipv4FromInterface("wlan0")
            when {
                ethIp != "N/A" -> "ethernet"
                wifiIp != "N/A" -> "wifi"
                else -> "none"
            }
        }
    }

    private fun ipv4FromInterface(interfaceName: String): String {
        return try {
            val iface = NetworkInterface.getByName(interfaceName) ?: return "N/A"
            iface.inetAddresses.toList().firstOrNull { it is Inet4Address && !it.isLoopbackAddress }
                ?.hostAddress ?: "N/A"
        } catch (_: Exception) {
            "N/A"
        }
    }

    private fun getMacAddressByInterface(interfaceName: String): String? {
        return try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val iface = interfaces.nextElement()
                if (iface.name.contains(interfaceName, ignoreCase = true)) {
                    val bytes = iface.hardwareAddress ?: continue
                    return bytes.joinToString(":") { "%02X".format(it) }
                }
            }
            null
        } catch (_: Exception) {
            null
        }
    }
}
