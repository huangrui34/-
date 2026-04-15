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

            // Try to register if not already
            api.registerIfNeeded("MeetingTV", networkInfo)

            // Send heartbeat and get policy
            val success = api.heartbeat(networkInfo)
            
            if (success) {
                val policy = policyStore.getPolicy()
                Log.d("SyncWorker", "Policy synced: ${policy.mode}")
                // Note: We don't execute the policy here directly to avoid 
                // interrupting the user if they are using the TV. 
                // Execution is usually triggered on boot or main app resume.
                Result.success()
            } else {
                Log.w("SyncWorker", "Heartbeat failed, will retry.")
                Result.retry()
            }
        } catch (e: Exception) {
            Log.e("SyncWorker", "Sync failed: ${e.message}")
            Result.retry()
        }
    }
}
