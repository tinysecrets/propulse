// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import android.app.Notification
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import ai.wahlah.propulse.ProPulse
import kotlinx.coroutines.cancelChildren
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Short-lived foreground service for sub-minute reactivity. Only runs while the
 * app is warm AND the battery governor allows it.
 */
class RealtimeChannelService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, buildNotification())
        scope.launch {
            while (isActive) {
                if (!ProPulse.isStarted()) break
                if (!ProPulse.governor.canUseRealtime()) break
                runCatching { PulseRegistry.flush(applicationContext, ProPulse.client) }
                delay(REALTIME_INTERVAL_MS)
            }
            stopSelf()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        scope.coroutineContext.cancelChildren()
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    private fun buildNotification(): Notification {
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, "propulse_default")
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        return builder
            .setContentTitle("ProPulse active")
            .setSmallIcon(android.R.drawable.ic_popup_reminder)
            .setOngoing(true)
            .build()
    }

    companion object {
        private const val NOTIFICATION_ID = 7710
        private const val REALTIME_INTERVAL_MS = 30_000L
    }
}
