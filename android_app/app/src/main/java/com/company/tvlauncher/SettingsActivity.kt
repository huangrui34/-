package com.company.tvlauncher

import android.os.Bundle
import android.net.wifi.WifiConfiguration
import android.net.wifi.WifiEnterpriseConfig
import android.net.wifi.WifiManager
import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import java.util.concurrent.Executors

class SettingsActivity : AppCompatActivity() {
    private val ioExecutor = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        val policyStore = PolicyStore(this)
        val networkInfo = NetworkInfoProvider(this).collect()
        findViewById<TextView>(R.id.networkInfoText).text =
            "WiFi MAC: ${networkInfo.wifiMac}\n" +
                "ETH MAC: ${networkInfo.ethMac}\n" +
                "SSID: ${networkInfo.ssid}\n" +
                "WiFi IP: ${networkInfo.wifiIp}\n" +
                "ETH IP: ${networkInfo.ethIp}"

        val serverEdit = findViewById<EditText>(R.id.serverUrlEdit)
        serverEdit.setText(policyStore.getServerBaseUrl())

        val passwordEdit = findViewById<EditText>(R.id.settingsPasswordEdit)
        passwordEdit.setText(policyStore.getSettingsPassword())

        val kioskSwitch = findViewById<Switch>(R.id.kioskSwitch)
        kioskSwitch.isChecked = policyStore.getKioskEnabled()
        kioskSwitch.setOnCheckedChangeListener { _, isChecked ->
            policyStore.setKioskEnabled(isChecked)
            Toast.makeText(this, if (isChecked) "已开启按键锁定（需在无障碍中启用服务）" else "已关闭按键锁定", Toast.LENGTH_SHORT).show()
        }

        findViewById<Button>(R.id.openAccessibilityBtn).setOnClickListener {
            try {
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            } catch (_: Exception) {
                Toast.makeText(this, "无法打开无障碍设置", Toast.LENGTH_SHORT).show()
            }
        }

        val modeSpinner = findViewById<Spinner>(R.id.modeSpinner)
        modeSpinner.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            listOf("app", "hdmi")
        )

        val appEdit = findViewById<EditText>(R.id.appPackageEdit)
        val hdmiEdit = findViewById<EditText>(R.id.hdmiPortEdit)
        val current = policyStore.getPolicy()
        appEdit.setText(current.targetAppPackage)
        hdmiEdit.setText(current.targetHdmiPort.toString())
        modeSpinner.setSelection(if (current.mode == "hdmi") 1 else 0)

        findViewById<Button>(R.id.registerBtn).setOnClickListener {
            policyStore.setServerBaseUrl(serverEdit.text.toString().ifBlank { "http://10.0.2.2:8000" })
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
                    Toast.makeText(
                        this,
                        if (okReg && okHb) "注册/同步成功" else "失败，请检查网络与后台地址",
                        Toast.LENGTH_SHORT
                    ).show()
                }
            }
        }

        findViewById<Button>(R.id.saveBtn).setOnClickListener {
            policyStore.setServerBaseUrl(serverEdit.text.toString().ifBlank { "http://10.0.2.2:8000" })
            policyStore.setSettingsPassword(passwordEdit.text.toString().ifBlank { "0000" })
            val mode = modeSpinner.selectedItem.toString()
            policyStore.savePolicy(
                LaunchPolicy(
                    mode = mode,
                    targetAppPackage = appEdit.text.toString().ifBlank { "com.example.cast" },
                    targetHdmiPort = hdmiEdit.text.toString().toIntOrNull() ?: 1
                )
            )
            finish()
        }

        // Enterprise Wi-Fi Connection
        findViewById<Button>(R.id.connectWifiBtn).setOnClickListener {
            val ssid = findViewById<EditText>(R.id.wifiSsidEdit).text.toString()
            val identity = findViewById<EditText>(R.id.wifiIdentityEdit).text.toString()
            val password = findViewById<EditText>(R.id.wifiPasswordEdit).text.toString()

            if (ssid.isBlank() || identity.isBlank() || password.isBlank()) {
                Toast.makeText(this, "请输入完整的 Wi-Fi 信息", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            connectToEnterpriseWifi(ssid, identity, password)
        }
    }

    private fun connectToEnterpriseWifi(ssid: String, identity: String, pass: String) {
        val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        if (!wifiManager.isWifiEnabled) {
            wifiManager.isWifiEnabled = true
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
        if (netId != -1) {
            wifiManager.disconnect()
            val success = wifiManager.enableNetwork(netId, true)
            wifiManager.reconnect()
            if (success) {
                Toast.makeText(this, "企业 Wi-Fi 配置已添加，正在尝试连接...", Toast.LENGTH_LONG).show()
            } else {
                Toast.makeText(this, "无法启用该网络配置", Toast.LENGTH_SHORT).show()
            }
        } else {
            Toast.makeText(this, "添加企业 Wi-Fi 网络失败 (可能已存在或格式错误)", Toast.LENGTH_SHORT).show()
        }
    }
}
