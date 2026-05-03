package com.company.tvlauncher

import android.app.AlertDialog
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.drawable.GradientDrawable
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.ScanResult
import android.net.wifi.WifiConfiguration
import android.net.wifi.WifiEnterpriseConfig
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class WifiConnectActivity : AppCompatActivity() {

    private lateinit var wifiManager: WifiManager
    private lateinit var wifiListContainer: LinearLayout
    private lateinit var statusText: TextView
    private lateinit var scanProgressBar: ProgressBar
    private lateinit var ethernetWarning: LinearLayout
    private lateinit var backButton: View
    private lateinit var wifiToggleBtn: TextView
    private lateinit var refreshBtn: TextView
    private val handler = Handler(Looper.getMainLooper())
    private val density by lazy { resources.displayMetrics.density }
    private fun dp(v: Int) = (v * density).toInt()

    private val FOCUS_BG = 0xFFE3F2FD.toInt()
    private val FOCUS_BORDER = 0xFF2196F3.toInt()
    private val NORMAL_BG = 0xFFFFFFFF.toInt()
    private val NORMAL_BORDER = 0xFFE0E0E0.toInt()

    private val scanReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == WifiManager.SCAN_RESULTS_AVAILABLE_ACTION) {
                showScanResults()
                scanProgressBar.visibility = ProgressBar.GONE
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager

        val scrollView = ScrollView(this).apply { setBackgroundColor(0xFFF0F2F5.toInt()) }
        val rootLayout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            val pad = dp(20)
            setPadding(pad, pad, pad, pad)
        }

        // 返回按钮
        backButton = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            background = roundedBg(NORMAL_BG, NORMAL_BORDER, dp(6))
            val pad2 = dp(12)
            setPadding(pad2, pad2, pad2, pad2)
            val margin = dp(6)
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                bottomMargin = margin
            }
            isClickable = true
            isFocusable = true
            setOnClickListener { finish() }
            onFocusChangeListener = View.OnFocusChangeListener { _, hasFocus ->
                background = if (hasFocus) roundedBg(FOCUS_BG, FOCUS_BORDER, dp(6)) else roundedBg(NORMAL_BG, NORMAL_BORDER, dp(6))
            }
            addView(TextView(context).apply {
                text = "← 返回"
                textSize = 16f
                setTextColor(0xFF3B82F6.toInt())
            })
        }
        rootLayout.addView(backButton)

        // 标题
        rootLayout.addView(TextView(this).apply {
            text = "WiFi 连接"
            textSize = 22f
            setTypeface(null, android.graphics.Typeface.BOLD)
            setTextColor(0xFF1F4E79.toInt())
        })

        // 有线网络警告
        ethernetWarning = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = roundedBg(0xFFFFF3CD.toInt(), 0xFFFFC107.toInt(), dp(6))
            val pad2 = dp(12)
            setPadding(pad2, pad2, pad2, pad2)
            val margin = dp(8)
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                topMargin = margin
                bottomMargin = margin
            }
            visibility = LinearLayout.GONE
        }
        ethernetWarning.addView(TextView(this).apply {
            text = "当前使用有线网络连接"
            textSize = 15f
            setTypeface(null, android.graphics.Typeface.BOLD)
            setTextColor(0xFF856404.toInt())
        })
        ethernetWarning.addView(TextView(this).apply {
            text = "小米电视连接有线时，WiFi会被系统自动关闭。如需连接WiFi，请先拔掉网线。"
            textSize = 13f
            setTextColor(0xFF856404.toInt())
        })
        rootLayout.addView(ethernetWarning)

        // WiFi开关行
        val wifiToggleLayout = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            val top = dp(12)
            setPadding(0, top, 0, 0)
        }

        wifiToggleBtn = TextView(this).apply {
            text = "WiFi: 检测中..."
            textSize = 16f
            setTextColor(0xFF2D3436.toInt())
            val pad2 = dp(10)
            setPadding(pad2, pad2, pad2, pad2)
            background = roundedBg(NORMAL_BG, NORMAL_BORDER, dp(6))
            isClickable = true
            isFocusable = true
            setOnClickListener { toggleWifi() }
            onFocusChangeListener = View.OnFocusChangeListener { _, hasFocus ->
                background = if (hasFocus) roundedBg(FOCUS_BG, FOCUS_BORDER, dp(6)) else roundedBg(NORMAL_BG, NORMAL_BORDER, dp(6))
            }
        }
        wifiToggleLayout.addView(wifiToggleBtn)

        refreshBtn = TextView(this).apply {
            text = "  刷新列表"
            textSize = 14f
            setTextColor(0xFF3B82F6.toInt())
            val pad2 = dp(10)
            setPadding(pad2, pad2, pad2, pad2)
            background = roundedBg(NORMAL_BG, NORMAL_BORDER, dp(6))
            isClickable = true
            isFocusable = true
            setOnClickListener { startScan() }
            onFocusChangeListener = View.OnFocusChangeListener { _, hasFocus ->
                background = if (hasFocus) roundedBg(FOCUS_BG, FOCUS_BORDER, dp(6)) else roundedBg(NORMAL_BG, NORMAL_BORDER, dp(6))
            }
        }
        wifiToggleLayout.addView(refreshBtn)

        rootLayout.addView(wifiToggleLayout)

        // 扫描进度
        scanProgressBar = ProgressBar(this).apply {
            visibility = ProgressBar.GONE
            val lp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp.gravity = Gravity.CENTER_HORIZONTAL
            layoutParams = lp
        }
        rootLayout.addView(scanProgressBar)

        // 状态文字
        statusText = TextView(this).apply {
            textSize = 14f
            setTextColor(0xFF636E72.toInt())
            val top2 = dp(8)
            setPadding(0, top2, 0, 0)
        }
        rootLayout.addView(statusText)

        // WiFi列表
        wifiListContainer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            val top3 = dp(8)
            setPadding(0, top3, 0, 0)
        }
        rootLayout.addView(wifiListContainer)

        scrollView.addView(rootLayout)
        setContentView(scrollView)

        registerReceiver(scanReceiver, IntentFilter(WifiManager.SCAN_RESULTS_AVAILABLE_ACTION))
        checkEthernetAndWifi()
    }

    override fun onDestroy() {
        super.onDestroy()
        try { unregisterReceiver(scanReceiver) } catch (_: Exception) {}
        handler.removeCallbacksAndMessages(null)
    }

    override fun onResume() {
        super.onResume()
        checkEthernetAndWifi()
    }

    private fun roundedBg(bgColor: Int, borderColor: Int, radius: Int): GradientDrawable {
        return GradientDrawable().apply {
            setColor(bgColor)
            setStroke(dp(2), borderColor)
            this.cornerRadius = radius.toFloat()
        }
    }

    private fun checkEthernetAndWifi() {
        val isEthernet = isEthernetConnected()
        val isWifiEnabled = wifiManager.isWifiEnabled

        ethernetWarning.visibility = if (isEthernet) LinearLayout.VISIBLE else LinearLayout.GONE

        if (isEthernet) {
            statusText.text = "检测到有线网络。WiFi连接需先拔掉网线，否则WiFi会被系统自动关闭。"
            wifiListContainer.removeAllViews()
            addEmptyHint("拔掉网线后点击「刷新列表」扫描WiFi")
        } else if (isWifiEnabled) {
            statusText.text = "WiFi已开启，扫描中..."
            startScan()
        } else {
            statusText.text = "WiFi未开启"
            wifiListContainer.removeAllViews()
            addEmptyHint("点击上方WiFi开关开启WiFi")
        }

        updateWifiToggleText()
    }

    private fun updateWifiToggleText() {
        val isWifiOn = wifiManager.isWifiEnabled
        wifiToggleBtn.text = if (isWifiOn) "WiFi: 已开启" else "WiFi: 已关闭"
        wifiToggleBtn.setTextColor(if (isWifiOn) 0xFF27AE60.toInt() else 0xFFE74C3C.toInt())
    }

    private fun toggleWifi() {
        if (isEthernetConnected()) {
            Toast.makeText(this, "请先拔掉网线，否则WiFi会被自动关闭", Toast.LENGTH_LONG).show()
            return
        }

        val newState = !wifiManager.isWifiEnabled
        wifiManager.isWifiEnabled = newState
        updateWifiToggleText()

        if (newState) {
            statusText.text = "WiFi开启中，请稍候..."
            handler.postDelayed({
                startScan()
                updateWifiToggleText()
                if (!wifiManager.isWifiEnabled && isEthernetConnected()) {
                    statusText.text = "WiFi被系统自动关闭了！请先拔掉网线。"
                    ethernetWarning.visibility = LinearLayout.VISIBLE
                }
            }, 3000)
        } else {
            statusText.text = "WiFi已关闭"
            wifiListContainer.removeAllViews()
        }
    }

    private fun isEthernetConnected(): Boolean {
        return try {
            val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val activeNetwork = cm.activeNetwork
            val caps = cm.getNetworkCapabilities(activeNetwork)
            caps?.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) == true
        } catch (_: Exception) {
            val netInfo = NetworkInfoProvider(this).collect()
            netInfo.ethIp != "0.0.0.0" && netInfo.ethIp != "N/A"
        }
    }

    private fun startScan() {
        if (!wifiManager.isWifiEnabled) {
            statusText.text = "WiFi未开启，请先开启WiFi"
            return
        }
        if (isEthernetConnected()) {
            statusText.text = "请先拔掉网线，否则WiFi会被自动关闭"
            return
        }

        scanProgressBar.visibility = ProgressBar.VISIBLE
        wifiListContainer.removeAllViews()
        statusText.text = "正在扫描WiFi..."

        showScanResults()
        wifiManager.startScan()
    }

    private fun isEnterpriseWifi(capabilities: String?): Boolean {
        if (capabilities.isNullOrBlank()) return false
        return capabilities.contains("EAP") || capabilities.contains("WPA2-EAP") || capabilities.contains("WPA-EAP")
    }

    private fun isSecuredWifi(capabilities: String?): Boolean {
        if (capabilities.isNullOrBlank()) return false
        return capabilities.contains("WPA") || capabilities.contains("WEP")
    }

    private fun getSecurityType(capabilities: String?): String {
        if (capabilities.isNullOrBlank()) return "开放"
        return when {
            isEnterpriseWifi(capabilities) -> "企业级"
            capabilities.contains("WPA2") -> "WPA2"
            capabilities.contains("WPA") -> "WPA"
            capabilities.contains("WEP") -> "WEP"
            else -> "开放"
        }
    }

    private fun showScanResults() {
        val results = wifiManager.scanResults ?: return
        val configured = wifiManager.configuredNetworks ?: emptyList()
        val currentSsid = wifiManager.connectionInfo?.ssid?.replace("\"", "") ?: ""

        wifiListContainer.removeAllViews()

        val seenSsids = mutableSetOf<String>()
        val uniqueResults = results
            .filter { it.SSID.isNotBlank() }
            .filter { seenSsids.add(it.SSID) }
            .sortedByDescending {
                if (it.SSID == currentSsid || it.SSID == "<unknown ssid>") Int.MAX_VALUE
                else it.level
            }

        if (uniqueResults.isEmpty()) {
            addEmptyHint("未发现WiFi网络，请确认WiFi已开启")
            return
        }

        for (scanResult in uniqueResults) {
            val isCurrent = scanResult.SSID == currentSsid
            val isEnterprise = isEnterpriseWifi(scanResult.capabilities)
            val isSecured = isSecuredWifi(scanResult.capabilities)

            val item = createWifiItem(scanResult, isCurrent, isSecured, isEnterprise)
            wifiListContainer.addView(item)
        }

        statusText.text = "发现 ${uniqueResults.size} 个WiFi网络"
    }

    private fun createWifiItem(scanResult: ScanResult, isCurrent: Boolean, isSecured: Boolean, isEnterprise: Boolean): LinearLayout {
        val itemPadding = dp(14)

        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = if (isCurrent) roundedBg(0xFFE8F8F5.toInt(), 0xFF27AE60.toInt(), dp(6)) else roundedBg(NORMAL_BG, NORMAL_BORDER, dp(6))
            setPadding(itemPadding, itemPadding, itemPadding, itemPadding)
            val margin = dp(4)
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                topMargin = margin
                bottomMargin = margin
            }

            isClickable = true
            isFocusable = true
            setOnClickListener {
                if (isCurrent) {
                    Toast.makeText(this@WifiConnectActivity, "已连接到 ${scanResult.SSID}", Toast.LENGTH_SHORT).show()
                } else if (isEnterprise) {
                    showEnterpriseDialog(scanResult)
                } else if (isSecured) {
                    showPasswordDialog(scanResult)
                } else {
                    connectToWifi(scanResult.SSID, "", false)
                }
            }
            onFocusChangeListener = View.OnFocusChangeListener { _, hasFocus ->
                background = if (hasFocus) roundedBg(FOCUS_BG, FOCUS_BORDER, dp(6))
                else if (isCurrent) roundedBg(0xFFE8F8F5.toInt(), 0xFF27AE60.toInt(), dp(6))
                else roundedBg(NORMAL_BG, NORMAL_BORDER, dp(6))
            }

            // 第一行：SSID + 安全标识 + 已连接
            val row1 = LinearLayout(context).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }

            row1.addView(TextView(context).apply {
                text = scanResult.SSID
                textSize = 16f
                setTextColor(0xFF2D3436.toInt())
                if (isCurrent) setTypeface(null, android.graphics.Typeface.BOLD)
            })

            // 安全类型标签
            val securityType = getSecurityType(scanResult.capabilities)
            if (isEnterprise) {
                row1.addView(TextView(context).apply {
                    text = "  企业级"
                    textSize = 12f
                    setTextColor(0xFFFFFFFF.toInt())
                    val pad2 = dp(4)
                    setPadding(pad2, dp(2), pad2, dp(2))
                    background = roundedBg(0xFF9C27B0.toInt(), 0xFF9C27B0.toInt(), dp(3))
                })
            } else if (isSecured) {
                row1.addView(TextView(context).apply {
                    text = "  $securityType"
                    textSize = 11f
                    setTextColor(0xFF636E72.toInt())
                })
            }

            if (isCurrent) {
                row1.addView(TextView(context).apply {
                    text = "  已连接"
                    textSize = 13f
                    setTextColor(0xFF27AE60.toInt())
                    setTypeface(null, android.graphics.Typeface.BOLD)
                })
            }

            addView(row1)

            // 第二行：信号 + 频段
            val row2 = LinearLayout(context).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                val top = dp(4)
                setPadding(0, top, 0, 0)
            }

            val signalLevel = WifiManager.calculateSignalLevel(scanResult.level, 4)
            val signalText = when (signalLevel) {
                3 -> "强"
                2 -> "中"
                1 -> "弱"
                else -> "极弱"
            }
            val signalColor = when (signalLevel) {
                3 -> 0xFF27AE60.toInt()
                2 -> 0xFFF39C12.toInt()
                1 -> 0xFFE67E22.toInt()
                else -> 0xFFE74C3C.toInt()
            }

            row2.addView(TextView(context).apply {
                text = signalText
                textSize = 12f
                setTextColor(signalColor)
            })
            row2.addView(TextView(context).apply {
                text = "(${scanResult.level}dBm)"
                textSize = 11f
                setTextColor(0xFF636E72.toInt())
            })

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                val freq = scanResult.frequency
                val bandText = if (freq > 5000) "5GHz" else "2.4GHz"
                row2.addView(TextView(context).apply {
                    text = "  $bandText"
                    textSize = 11f
                    setTextColor(0xFF636E72.toInt())
                })
            }

            addView(row2)
        }
    }

    private fun showPasswordDialog(scanResult: ScanResult) {
        val input = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            hint = "输入WiFi密码"
            textSize = 16f
            val pad = dp(12)
            setPadding(pad, pad, pad, pad)
            background = roundedBg(0xFFFFFFFF.toInt(), 0xFFBDBDBD.toInt(), dp(4))
        }
        val container = FrameLayout(this).apply {
            val params = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
            )
            params.setMargins(60, 20, 60, 20)
            addView(input, params)
        }

        AlertDialog.Builder(this)
            .setTitle("连接 ${scanResult.SSID}")
            .setView(container)
            .setPositiveButton("连接") { _, _ ->
                val password = input.text.toString()
                if (password.isBlank()) {
                    Toast.makeText(this, "请输入密码", Toast.LENGTH_SHORT).show()
                    return@setPositiveButton
                }
                connectToWifi(scanResult.SSID, password, true)
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun showEnterpriseDialog(scanResult: ScanResult) {
        val inputBg = roundedBg(0xFFFFFFFF.toInt(), 0xFFBDBDBD.toInt(), dp(4))

        val identityInput = EditText(this).apply {
            hint = "用户名 (Identity)"
            textSize = 16f
            val pad = dp(12)
            setPadding(pad, pad, pad, pad)
            background = inputBg
        }
        val passwordInput = EditText(this).apply {
            hint = "密码"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            textSize = 16f
            val pad = dp(12)
            setPadding(pad, pad, pad, pad)
            background = inputBg
        }

        val dialogLayout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            val pad = dp(16)
            setPadding(pad, pad, pad, pad)

            addView(TextView(context).apply {
                text = "此网络为企业级WiFi (802.1X/EAP)"
                textSize = 13f
                setTextColor(0xFF9C27B0.toInt())
                val bottom = dp(8)
                setPadding(0, 0, 0, bottom)
            })
            addView(identityInput)
            val margin = dp(8)
            (identityInput.layoutParams as? LinearLayout.LayoutParams)?.bottomMargin = margin
            addView(passwordInput)
        }

        AlertDialog.Builder(this)
            .setTitle("连接 ${scanResult.SSID}")
            .setView(dialogLayout)
            .setPositiveButton("连接") { _, _ ->
                val identity = identityInput.text.toString()
                val password = passwordInput.text.toString()
                if (identity.isBlank() || password.isBlank()) {
                    Toast.makeText(this, "请输入用户名和密码", Toast.LENGTH_SHORT).show()
                    return@setPositiveButton
                }
                connectToEnterpriseWifi(scanResult.SSID, identity, password)
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun connectToWifi(ssid: String, password: String, isSecured: Boolean) {
        if (isEthernetConnected()) {
            Toast.makeText(this, "请先拔掉网线，否则WiFi会被自动关闭", Toast.LENGTH_LONG).show()
            return
        }

        statusText.text = "正在连接 $ssid ..."

        wifiManager.configuredNetworks?.filter { it.SSID == "\"$ssid\"" }?.forEach {
            wifiManager.removeNetwork(it.networkId)
        }

        val wifiConfig = WifiConfiguration().apply {
            SSID = "\"$ssid\""
            status = WifiConfiguration.Status.ENABLED
            if (isSecured) {
                allowedKeyManagement.set(WifiConfiguration.KeyMgmt.WPA_PSK)
                preSharedKey = "\"$password\""
            } else {
                allowedKeyManagement.set(WifiConfiguration.KeyMgmt.NONE)
            }
        }

        val netId = wifiManager.addNetwork(wifiConfig)
        if (netId == -1) {
            statusText.text = "添加网络配置失败"
            return
        }

        wifiManager.disconnect()
        wifiManager.enableNetwork(netId, true)
        wifiManager.reconnect()

        handler.postDelayed({
            val info = wifiManager.connectionInfo
            val connectedSsid = info?.ssid?.replace("\"", "") ?: ""
            if (connectedSsid == ssid) {
                statusText.text = "已连接到 $ssid"
                showScanResults()
            } else {
                statusText.text = "连接 $ssid 失败，请检查密码是否正确"
            }
        }, 8000)
    }

    private fun connectToEnterpriseWifi(ssid: String, identity: String, pass: String) {
        if (isEthernetConnected()) {
            Toast.makeText(this, "请先拔掉网线，否则WiFi会被自动关闭", Toast.LENGTH_LONG).show()
            return
        }

        statusText.text = "正在连接企业WiFi $ssid ..."

        wifiManager.configuredNetworks?.filter { it.SSID == "\"$ssid\"" }?.forEach {
            wifiManager.removeNetwork(it.networkId)
        }

        val enterpriseConfig = WifiEnterpriseConfig().apply {
            setIdentity(identity)
            setPassword(pass)
            eapMethod = WifiEnterpriseConfig.Eap.PEAP
            phase2Method = WifiEnterpriseConfig.Phase2.MSCHAPV2
        }

        val wifiConfig = WifiConfiguration().apply {
            SSID = "\"$ssid\""
            status = WifiConfiguration.Status.ENABLED
            allowedKeyManagement.set(WifiConfiguration.KeyMgmt.WPA_EAP)
            allowedKeyManagement.set(WifiConfiguration.KeyMgmt.IEEE8021X)
            this.enterpriseConfig = enterpriseConfig
        }

        val netId = wifiManager.addNetwork(wifiConfig)
        if (netId == -1) {
            statusText.text = "添加企业网络配置失败"
            return
        }

        wifiManager.disconnect()
        wifiManager.enableNetwork(netId, true)
        wifiManager.reconnect()

        handler.postDelayed({
            val info = wifiManager.connectionInfo
            val connectedSsid = info?.ssid?.replace("\"", "") ?: ""
            if (connectedSsid == ssid) {
                statusText.text = "已连接到企业WiFi $ssid"
                showScanResults()
            } else {
                statusText.text = "连接 $ssid 失败，请检查用户名和密码"
            }
        }, 8000)
    }

    private fun addEmptyHint(text: String) {
        wifiListContainer.addView(TextView(this).apply {
            this.text = text
            textSize = 14f
            setTextColor(0xFF636E72.toInt())
            gravity = Gravity.CENTER
            val top = dp(24)
            setPadding(0, top, 0, 0)
        })
    }
}
