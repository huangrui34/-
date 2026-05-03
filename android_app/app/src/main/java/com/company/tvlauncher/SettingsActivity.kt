package com.company.tvlauncher

import android.app.ActivityManager
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Build
import android.os.Environment
import android.os.StatFs
import android.net.wifi.WifiConfiguration
import android.net.wifi.WifiEnterpriseConfig
import android.net.wifi.WifiManager
import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import java.util.concurrent.Executors

class SettingsActivity : AppCompatActivity() {
    private val ioExecutor = Executors.newSingleThreadExecutor()
    private lateinit var menuContainer: LinearLayout
    private val density by lazy { resources.displayMetrics.density }
    private fun dp(v: Int) = (v * density).toInt()

    // 焦点颜色
    private val FOCUS_BG = 0xFFE3F2FD.toInt()       // 浅蓝背景
    private val FOCUS_BORDER = 0xFF2196F3.toInt()    // 蓝色边框
    private val NORMAL_BG = 0xFFFFFFFF.toInt()       // 白色背景
    private val NORMAL_BORDER = 0xFFE0E0E0.toInt()   // 灰色边框

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val scrollView = ScrollView(this).apply { setBackgroundColor(0xFFF0F2F5.toInt()) }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(20), dp(24), dp(20))
        }

        root.addView(TextView(this).apply {
            text = "设置"
            textSize = 24f
            setTextColor(0xFF1F4E79.toInt())
            setTypeface(null, android.graphics.Typeface.BOLD)
        })

        menuContainer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            val top = dp(16)
            setPadding(0, top, 0, 0)
        }
        root.addView(menuContainer)
        scrollView.addView(root)
        setContentView(scrollView)

        showMainMenu()
    }

    private fun showMainMenu() {
        menuContainer.removeAllViews()
        val policyStore = PolicyStore(this)
        val policy = policyStore.getPolicy()

        val items = listOf(
            Triple("WiFi 连接", "扫描并连接WiFi网络", View.OnClickListener {
                startActivity(Intent(this, WifiConnectActivity::class.java))
            }),
            Triple("策略配置", "当前: ${if (policy.mode == "hdmi") "HDMI${policy.targetHdmiPort}" else policy.targetAppPackage?.split(".")?.lastOrNull() ?: "未设置"}", View.OnClickListener {
                showPolicyPage()
            }),
            Triple("服务器连接", policyStore.getServerBaseUrl(), View.OnClickListener {
                showServerPage()
            }),
            Triple("按键锁定", if (policyStore.getKioskEnabled()) "已开启" else "已关闭", View.OnClickListener {
                showKioskPage()
            }),
            Triple("管理密码", "修改管理锁密码", View.OnClickListener {
                showPasswordPage()
            }),
            Triple("企业WiFi (802.1X)", "PEAP/MSCHAPv2企业网络", View.OnClickListener {
                showEnterpriseWifiPage()
            }),
            Triple("关于本机", "查看设备信息", View.OnClickListener {
                showAboutPage()
            })
        )

        for ((title, subtitle, listener) in items) {
            menuContainer.addView(createMenuItem(title, subtitle, listener))
        }
    }

    private fun createMenuItem(title: String, subtitle: String, listener: View.OnClickListener): View {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = roundedBg(NORMAL_BG, NORMAL_BORDER, dp(6))
            val pad = dp(16)
            setPadding(pad, pad, pad, pad)
            val margin = dp(6)
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                topMargin = margin
                bottomMargin = margin
            }
            isClickable = true
            isFocusable = true
            setOnClickListener(listener)
            onFocusChangeListener = View.OnFocusChangeListener { v, hasFocus ->
                background = if (hasFocus) roundedBg(FOCUS_BG, FOCUS_BORDER, dp(6)) else roundedBg(NORMAL_BG, NORMAL_BORDER, dp(6))
            }

            addView(TextView(context).apply {
                text = title
                textSize = 17f
                setTextColor(0xFF2D3436.toInt())
            })
            addView(TextView(context).apply {
                text = subtitle
                textSize = 13f
                setTextColor(0xFF636E72.toInt())
                val top = dp(4)
                setPadding(0, top, 0, 0)
            })
        }
    }

    private fun roundedBg(bgColor: Int, borderColor: Int, radius: Int): GradientDrawable {
        return GradientDrawable().apply {
            setColor(bgColor)
            setStroke(dp(2), borderColor)
            this.cornerRadius = radius.toFloat()
        }
    }

    private fun showPolicyPage() {
        menuContainer.removeAllViews()
        val policyStore = PolicyStore(this)
        val policy = policyStore.getPolicy()

        addBackButton()

        menuContainer.addView(createMenuItem("APP模式", if (policy.mode == "app") "当前 → ${policy.targetAppPackage}" else "点击切换", View.OnClickListener {
            showAppModeEdit(policy.targetAppPackage ?: "")
        }))
        menuContainer.addView(createMenuItem("HDMI模式", if (policy.mode == "hdmi") "当前 → HDMI${policy.targetHdmiPort}" else "点击切换", View.OnClickListener {
            showHdmiModeEdit(policy.targetHdmiPort)
        }))
    }

    private fun showAppModeEdit(currentPkg: String) {
        menuContainer.removeAllViews()
        addBackButton { showPolicyPage() }

        val input = EditText(this).apply {
            setText(currentPkg)
            hint = "目标APP包名"
            textSize = 16f
            setPadding(dp(12), dp(12), dp(12), dp(12))
            background = roundedBg(0xFFFFFFFF.toInt(), 0xFFBDBDBD.toInt(), dp(4))
        }
        menuContainer.addView(input)

        menuContainer.addView(createMenuItem("保存并启用APP模式", "", View.OnClickListener {
            val pkg = input.text.toString().ifBlank { "com.example.cast" }
            PolicyStore(this).savePolicy(LaunchPolicy(mode = "app", targetAppPackage = pkg, targetHdmiPort = 1))
            Toast.makeText(this, "已保存: APP模式 → $pkg", Toast.LENGTH_SHORT).show()
            showMainMenu()
        }))
    }

    private fun showHdmiModeEdit(currentPort: Int) {
        menuContainer.removeAllViews()
        addBackButton { showPolicyPage() }

        val items = listOf(1, 2, 3).map { port ->
            Triple("HDMI $port", if (currentPort == port) "当前" else "", View.OnClickListener {
                PolicyStore(this).savePolicy(LaunchPolicy(mode = "hdmi", targetAppPackage = "", targetHdmiPort = port))
                Toast.makeText(this, "已保存: HDMI模式 → HDMI $port", Toast.LENGTH_SHORT).show()
                showMainMenu()
            })
        }
        for ((title, subtitle, listener) in items) {
            menuContainer.addView(createMenuItem(title, subtitle, listener))
        }
    }

    private fun showServerPage() {
        menuContainer.removeAllViews()
        addBackButton()

        val policyStore = PolicyStore(this)
        val input = EditText(this).apply {
            setText(policyStore.getServerBaseUrl())
            hint = "http://192.168.1.10:8000"
            textSize = 16f
            setPadding(dp(12), dp(12), dp(12), dp(12))
            background = roundedBg(0xFFFFFFFF.toInt(), 0xFFBDBDBD.toInt(), dp(4))
        }
        menuContainer.addView(input)

        menuContainer.addView(createMenuItem("保存服务器地址", "", View.OnClickListener {
            policyStore.setServerBaseUrl(input.text.toString().ifBlank { "http://10.0.2.2:8000" })
            Toast.makeText(this, "服务器地址已保存", Toast.LENGTH_SHORT).show()
            showMainMenu()
        }))

        menuContainer.addView(createMenuItem("注册并同步", "向后台注册设备并同步策略", View.OnClickListener {
            policyStore.setServerBaseUrl(input.text.toString().ifBlank { "http://10.0.2.2:8000" })
            ioExecutor.execute {
                val net = NetworkInfoProvider(this).collect()
                val api = RemoteApi(this, policyStore)
                val okReg = api.registerIfNeeded("MeetingTV", net)
                var okHb = api.heartbeat(net)
                if (!okHb) {
                    policyStore.clearDeviceToken()
                    api.registerIfNeeded("MeetingTV", net)
                    okHb = api.heartbeat(net)
                }
                runOnUiThread {
                    Toast.makeText(this, if (okReg && okHb) "注册/同步成功" else "失败，请检查网络与后台地址", Toast.LENGTH_SHORT).show()
                }
            }
        }))
    }

    private fun showKioskPage() {
        menuContainer.removeAllViews()
        addBackButton()

        val policyStore = PolicyStore(this)
        val isOn = policyStore.getKioskEnabled()

        menuContainer.addView(createMenuItem("开启按键锁定", "锁定返回键，需在无障碍中启用服务", View.OnClickListener {
            policyStore.setKioskEnabled(true)
            Toast.makeText(this, "已开启，需在无障碍中启用服务", Toast.LENGTH_SHORT).show()
            showKioskPage()
        }))
        menuContainer.addView(createMenuItem("关闭按键锁定", "", View.OnClickListener {
            policyStore.setKioskEnabled(false)
            Toast.makeText(this, "已关闭按键锁定", Toast.LENGTH_SHORT).show()
            showKioskPage()
        }))
        menuContainer.addView(createMenuItem("打开无障碍设置", "系统设置 → 无障碍", View.OnClickListener {
            try { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
            catch (_: Exception) { Toast.makeText(this, "无法打开", Toast.LENGTH_SHORT).show() }
        }))

        val statusText = TextView(this).apply {
            text = "当前状态: ${if (isOn) "已开启" else "已关闭"}"
            textSize = 14f
            setTextColor(if (isOn) 0xFF27AE60.toInt() else 0xFF636E72.toInt())
            val pad = dp(12)
            setPadding(pad, pad, pad, pad)
        }
        menuContainer.addView(statusText)
    }

    private fun showPasswordPage() {
        menuContainer.removeAllViews()
        addBackButton()

        val input = EditText(this).apply {
            inputType = android.text.InputType.TYPE_CLASS_NUMBER or android.text.InputType.TYPE_NUMBER_VARIATION_PASSWORD
            hint = "输入新的4位管理密码"
            textSize = 16f
            setPadding(dp(12), dp(12), dp(12), dp(12))
            background = roundedBg(0xFFFFFFFF.toInt(), 0xFFBDBDBD.toInt(), dp(4))
        }
        menuContainer.addView(input)

        menuContainer.addView(createMenuItem("保存密码", "", View.OnClickListener {
            val pwd = input.text.toString().ifBlank { "0000" }
            PolicyStore(this).setSettingsPassword(pwd)
            Toast.makeText(this, "密码已更新", Toast.LENGTH_SHORT).show()
            showMainMenu()
        }))
    }

    private fun showEnterpriseWifiPage() {
        menuContainer.removeAllViews()
        addBackButton()

        val inputBg = roundedBg(0xFFFFFFFF.toInt(), 0xFFBDBDBD.toInt(), dp(4))
        val ssidInput = EditText(this).apply { hint = "WiFi SSID"; textSize = 16f; setPadding(dp(12), dp(12), dp(12), dp(12)); background = inputBg }
        val identityInput = EditText(this).apply { hint = "用户名 (Identity)"; textSize = 16f; setPadding(dp(12), dp(12), dp(12), dp(12)); background = inputBg }
        val passwordInput = EditText(this).apply { hint = "密码"; inputType = android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD; textSize = 16f; setPadding(dp(12), dp(12), dp(12), dp(12)); background = inputBg }

        menuContainer.addView(ssidInput)
        menuContainer.addView(identityInput)
        menuContainer.addView(passwordInput)

        menuContainer.addView(createMenuItem("连接企业WiFi", "PEAP/MSCHAPv2", View.OnClickListener {
            val ssid = ssidInput.text.toString()
            val identity = identityInput.text.toString()
            val password = passwordInput.text.toString()
            if (ssid.isBlank() || identity.isBlank() || password.isBlank()) {
                Toast.makeText(this, "请填写完整信息", Toast.LENGTH_SHORT).show()
                return@OnClickListener
            }
            connectToEnterpriseWifi(ssid, identity, password)
        }))
    }

    private fun showAboutPage() {
        menuContainer.removeAllViews()
        addBackButton()

        val packageInfo = packageManager.getPackageInfo(packageName, 0)
        val serial = try { Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID) ?: "N/A" } catch (_: Exception) { "N/A" }

        addSectionTitle("设备信息")
        addItemRow("型号", Build.MODEL)
        addItemRow("Android", "${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})")
        addItemRow("序列号", serial)
        addItemRow("APP版本", packageInfo.versionName)

        addSectionTitle("网络信息")
        addItemRow("加载中...", "")

        addSectionTitle("系统信息")
        addItemRow("加载中...", "")

        ioExecutor.execute {
            val networkInfo = NetworkInfoProvider(this).collect()
            val policyStore = PolicyStore(this)

            val ramInfo = try {
                val am = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
                val mi = ActivityManager.MemoryInfo()
                am.getMemoryInfo(mi)
                "${(mi.totalMem - mi.availMem) / (1024 * 1024)}MB / ${mi.totalMem / (1024 * 1024)}MB"
            } catch (_: Exception) { "N/A" }

            val storageInfo = try {
                val stat = StatFs(Environment.getDataDirectory().path)
                val total = (stat.blockCountLong * stat.blockSizeLong) / (1024 * 1024)
                val avail = (stat.availableBlocksLong * stat.blockSizeLong) / (1024 * 1024)
                "${total - avail}MB / ${total}MB"
            } catch (_: Exception) { "N/A" }

            runOnUiThread {
                menuContainer.removeAllViews()
                addBackButton()

                addSectionTitle("设备信息")
                addItemRow("型号", Build.MODEL)
                addItemRow("Android", "${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})")
                addItemRow("序列号", serial)
                addItemRow("APP版本", packageInfo.versionName)

                addSectionTitle("网络信息")
                addItemRow("WiFi IP", networkInfo.wifiIp)
                addItemRow("有线IP", networkInfo.ethIp)
                addItemRow("WiFi MAC", networkInfo.wifiMac)
                addItemRow("有线MAC", networkInfo.ethMac)
                addItemRow("SSID", networkInfo.ssid)
                addItemRow("网络类型", networkInfo.networkType)
                if (networkInfo.wifiRssi > -127) {
                    addItemRow("WiFi信号", "${networkInfo.wifiRssi}dBm")
                    addItemRow("WiFi频段", if (networkInfo.wifiFrequency > 5000) "5GHz" else "2.4GHz")
                    addItemRow("WiFi速度", "${networkInfo.wifiLinkSpeed}Mbps")
                }
                if (networkInfo.pingLatency >= 0) addItemRow("延迟", "${networkInfo.pingLatency}ms")
                if (networkInfo.pingPacketLoss >= 0) addItemRow("丢包", "${networkInfo.pingPacketLoss}%")

                addSectionTitle("系统信息")
                addItemRow("内存", ramInfo)
                addItemRow("存储", storageInfo)
                addItemRow("服务器", policyStore.getServerBaseUrl())
            }
        }
    }

    private fun addBackButton(action: (() -> Unit)? = null) {
        val btn = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            background = roundedBg(NORMAL_BG, NORMAL_BORDER, dp(6))
            val pad = dp(12)
            setPadding(pad, pad, pad, pad)
            val margin = dp(6)
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                topMargin = margin
                bottomMargin = margin
            }
            isClickable = true
            isFocusable = true
            setOnClickListener { action?.invoke() ?: showMainMenu() }
            onFocusChangeListener = View.OnFocusChangeListener { v, hasFocus ->
                background = if (hasFocus) roundedBg(FOCUS_BG, FOCUS_BORDER, dp(6)) else roundedBg(NORMAL_BG, NORMAL_BORDER, dp(6))
            }

            addView(TextView(context).apply {
                text = "← 返回"
                textSize = 16f
                setTextColor(0xFF3B82F6.toInt())
            })
        }
        menuContainer.addView(btn)
    }

    private fun addSectionTitle(title: String) {
        menuContainer.addView(TextView(this).apply {
            text = title
            textSize = 14f
            setTextColor(0xFF1F4E79.toInt())
            setTypeface(null, android.graphics.Typeface.BOLD)
            val pad = dp(8)
            setPadding(0, dp(16), 0, pad)
        })
    }

    private fun addItemRow(label: String, value: String) {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            background = roundedBg(NORMAL_BG, NORMAL_BORDER, dp(4))
            val pad = dp(12)
            setPadding(pad, dp(8), pad, dp(8))
            val margin = dp(2)
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                topMargin = margin
                bottomMargin = margin
            }
        }
        row.addView(TextView(this).apply {
            text = label
            textSize = 14f
            setTextColor(0xFF2D3436.toInt())
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 0.4f)
        })
        row.addView(TextView(this).apply {
            text = value
            textSize = 14f
            setTextColor(0xFF636E72.toInt())
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 0.6f)
        })
        menuContainer.addView(row)
    }

    private fun connectToEnterpriseWifi(ssid: String, identity: String, pass: String) {
        val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        if (!wifiManager.isWifiEnabled) wifiManager.isWifiEnabled = true

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
        if (netId != -1) {
            wifiManager.disconnect()
            wifiManager.enableNetwork(netId, true)
            wifiManager.reconnect()
            Toast.makeText(this, "企业WiFi配置已添加，正在连接...", Toast.LENGTH_LONG).show()
        } else {
            Toast.makeText(this, "添加网络失败", Toast.LENGTH_SHORT).show()
        }
    }
}
