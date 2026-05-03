package com.company.tvlauncher

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class SyncWorker(
    context: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(context, workerParams) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        try {
            val policyStore = PolicyStore(applicationContext)
            val networkProvider = NetworkInfoProvider(applicationContext)
            val networkInfo = networkProvider.collect()
            val api = RemoteApi(applicationContext, policyStore)

            // 如果没有token，说明尚未注册或已被注销，需要重新注册
            val hasToken = policyStore.getDeviceToken() != null
            if (!hasToken) {
                val registered = api.registerIfNeeded("MeetingTV", networkInfo)
                if (!registered) {
                    Log.w("SyncWorker", "注册失败，将在下次重试")
                    return@withContext Result.retry()
                }
            }

            // 发送心跳
            val success = api.heartbeat(networkInfo)

            if (success) {
                val policy = policyStore.getPolicy()
                Log.d("SyncWorker", "Policy synced: ${policy.mode}")
                Result.success()
            } else {
                // 心跳失败 + WiFi切换进行中 = 新WiFi不可达，回退
                if (policyStore.isWifiSwitchInProgress()) {
                    val elapsed = System.currentTimeMillis() - policyStore.getWifiSwitchStartTime()
                    if (elapsed > 10_000) {
                        Log.w("SyncWorker", "Heartbeat failed after WiFi switch, reverting")
                        val wifiManager = WifiConfigManager(applicationContext)
                        wifiManager.revertToNetwork(policyStore.getWifiRevertNetworkId())
                        policyStore.clearWifiSwitchState()
                        policyStore.setLastAppliedWifiConfig(null)
                    }
                }
                // 心跳失败：可能是服务器不可达，也可能是token失效（设备被移除）
                // 清除token，下次SyncWorker运行时会重新注册
                Log.w("SyncWorker", "心跳失败，清除token等待重新注册")
                policyStore.clearDeviceToken()
                Result.retry()
            }
        } catch (e: Exception) {
            Log.e("SyncWorker", "Sync failed: ${e.message}")
            Result.retry()
        }
    }
}
