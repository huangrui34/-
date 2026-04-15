package com.company.tvlauncher

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED || 
            intent?.action == "android.intent.action.QUICKBOOT_POWERON") {
            
            // For older/slow devices, give the system a bit more time to settle
            // but start the launcher as early as possible.
            val handler = Handler(Looper.getMainLooper())
            handler.postDelayed({
                val policyStore = PolicyStore(context)
                val launchIntent = Intent(context, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or 
                             Intent.FLAG_ACTIVITY_CLEAR_TOP or
                             Intent.FLAG_ACTIVITY_SINGLE_TOP)
                }
                context.startActivity(launchIntent)
                
                // Directly execute policy from boot to minimize delay
                LauncherExecutor(context).execute(policyStore.getPolicy())
            }, 3000) // Reduced from 5s to 3s for faster startup
        }
    }
}
