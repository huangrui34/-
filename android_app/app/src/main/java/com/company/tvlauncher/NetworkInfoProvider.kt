package com.company.tvlauncher

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.text.format.Formatter
import java.net.Inet4Address
import java.net.NetworkInterface
import java.net.URI

data class TvNetworkInfo(
    val wifiMac: String,
    val ethMac: String,
    val ssid: String,
    val wifiIp: String,
    val ethIp: String,
    val networkType: String,  // "wifi" | "ethernet" | "none"
    val wifiRssi: Int = 0,
    val wifiFrequency: Int = 0,
    val wifiLinkSpeed: Int = 0,
    val pingLatency: Int = -1,
    val pingPacketLoss: Int = -1
)

class NetworkInfoProvider(private val context: Context) {
    companion object {
        private const val TAG = "NetworkInfoProvider"
    }

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

        // WiFi signal quality metrics
        val wifiRssi = info?.rssi ?: 0
        val wifiLinkSpeed = info?.linkSpeed ?: 0
        val wifiFrequency = try {
            // Android 9+ (API 28+) supports getFrequency()
            val method = info?.javaClass?.getMethod("getFrequency")
            method?.invoke(info) as? Int ?: 0
        } catch (_: Exception) { 0 }

        // Ping test for latency and packet loss
        val pingResult = pingTest()

        return TvNetworkInfo(
            wifiMac = getMacAddressByInterface("wlan0") ?: getMacAddressByInterface("p2p-wlan0-0") ?: "N/A",
            ethMac = getMacAddressByInterface("eth0") ?: "N/A",
            ssid = if (ssid == "<unknown ssid>" || ssid.isBlank()) "未连接" else ssid,
            wifiIp = wifiIp,
            ethIp = ethIp,
            networkType = networkType,
            wifiRssi = wifiRssi,
            wifiFrequency = wifiFrequency,
            wifiLinkSpeed = wifiLinkSpeed,
            pingLatency = pingResult.first,
            pingPacketLoss = pingResult.second
        )
    }

    /**
     * 网络延迟测试
     * 优先ICMP ping，失败则用TCP连接测延迟
     * Returns (latency_ms, packet_loss_percent)
     */
    private fun pingTest(): Pair<Int, Int> {
        val gateway = getGatewayIp()
        val serverIp = getServerIp()

        // 尝试ICMP ping
        val targets = mutableListOf<String>()
        if (gateway != null) targets.add(gateway)
        if (serverIp != null && serverIp != gateway) targets.add(serverIp)

        for (target in targets) {
            val result = pingHost(target)
            if (result.first >= 0) return result
        }

        // ICMP ping全部失败，改用TCP连接测延迟（ping服务器端口8000）
        val tcpTarget = serverIp ?: gateway
        if (tcpTarget != null) {
            val tcpLatency = tcpPingTest(tcpTarget, 8000)
            if (tcpLatency >= 0) return Pair(tcpLatency, 0)
        }

        return Pair(-1, -1)
    }

    private fun pingHost(host: String): Pair<Int, Int> {
        return try {
            val process = Runtime.getRuntime().exec(
                arrayOf("ping", "-c", "3", "-W", "2", host)
            )
            val output = process.inputStream.bufferedReader().readText()
            process.waitFor()

            val latencyRegex = Regex("""= [\d.]+/([\d.]+)/[\d.]+/[\d.]+ ms""")
            val avgLatency = latencyRegex.find(output)?.groupValues?.get(1)?.toInt() ?: -1

            val lossRegex = Regex("""(\d+)% packet loss""")
            val packetLoss = lossRegex.find(output)?.groupValues?.get(1)?.toInt() ?: -1

            android.util.Log.d(TAG, "Ping $host: latency=${avgLatency}ms, loss=${packetLoss}%")
            Pair(avgLatency, packetLoss)
        } catch (e: Exception) {
            android.util.Log.d(TAG, "Ping $host failed: ${e.message}")
            Pair(-1, -1)
        }
    }

    /**
     * TCP连接测延迟：连接目标IP的指定端口，测量连接耗时
     */
    private fun tcpPingTest(host: String, port: Int): Int {
        return try {
            val start = System.currentTimeMillis()
            val socket = java.net.Socket()
            socket.connect(java.net.InetSocketAddress(host, port), 3000)
            val latency = (System.currentTimeMillis() - start).toInt()
            socket.close()
            android.util.Log.d(TAG, "TCP ping $host:$port = ${latency}ms")
            latency
        } catch (e: Exception) {
            android.util.Log.d(TAG, "TCP ping $host:$port failed: ${e.message}")
            -1
        }
    }

    /**
     * 获取心跳服务器IP地址
     */
    private fun getServerIp(): String? {
        return try {
            val baseUrl = PolicyStore(context).getServerBaseUrl() ?: return null
            val uri = java.net.URI(baseUrl)
            uri.host
        } catch (_: Exception) { null }
    }

    /**
     * Get the default gateway IP address
     */
    private fun getGatewayIp(): String? {
        return try {
            // Method 1: From WifiManager (works for WiFi connections)
            val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            val dhcpInfo = wifiManager.dhcpInfo
            if (dhcpInfo != null && dhcpInfo.gateway != 0) {
                val gateway = dhcpInfo.gateway
                return Formatter.formatIpAddress(gateway)
            }

            // Method 2: Parse /proc/net/route
            try {
                val routes = java.io.File("/proc/net/route").readLines()
                for (line in routes.drop(1)) {
                    val cols = line.split(Regex("\\s+"))
                    if (cols.size > 2 && cols[1] == "00000000") {
                        val hex = cols[2]
                        if (hex.length >= 8) {
                            val ip = "${hex.substring(6, 8).toInt(16)}.${hex.substring(4, 6).toInt(16)}.${hex.substring(2, 4).toInt(16)}.${hex.substring(0, 2).toInt(16)}"
                            return ip
                        }
                    }
                }
            } catch (_: Exception) {}

            null
        } catch (e: Exception) {
            null
        }
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
