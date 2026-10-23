// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import ai.wahlah.propulse.Priority
import ai.wahlah.propulse.ProPulse
import ai.wahlah.propulse.Trigger
import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.SystemClock

/**
 * One-shot trigger receiver for integrations that need a device-local deadline.
 * Uses exact idle-aware alarms only when the host app has been granted that special access;
 * otherwise it safely falls back to Android's idle-aware inexact alarm.
 */
class AlarmReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != ACTION_TRIGGER) return
        if (!ProPulse.isStarted()) ProPulse.autoStart(context.applicationContext)
        if (!ProPulse.isStarted()) return

        val key = intent.getStringExtra(EXTRA_PULSE_KEY)?.takeIf { it.isNotBlank() } ?: return
        val ttl = intent.getLongExtra(EXTRA_TTL_SECONDS, DEFAULT_TTL_SECONDS)
            .coerceAtLeast(1L)
        val priorityWire = intent.getStringExtra(EXTRA_PRIORITY)
        val priority = Priority.entries.firstOrNull { it.wire == priorityWire }
            ?: Priority.NORMAL
        ProPulse.trigger(Trigger.Signal(key), ttl, priority)
    }

    companion object {
        const val ACTION_TRIGGER = "ai.wahlah.propulse.ACTION_TRIGGER_ALARM"
        private const val EXTRA_PULSE_KEY = "pulse_key"
        private const val EXTRA_TTL_SECONDS = "ttl_seconds"
        private const val EXTRA_PRIORITY = "priority"
        private const val DEFAULT_TTL_SECONDS = 3600L

        /** Schedule one trigger at a relative elapsed-realtime deadline. */
        @JvmStatic
        fun scheduleTrigger(
            context: Context,
            pulseKey: String,
            delaySeconds: Long,
            ttlSeconds: Long = DEFAULT_TTL_SECONDS,
            priority: Priority = Priority.NORMAL,
        ) {
            require(pulseKey.isNotBlank()) { "pulseKey must not be blank" }
            require(delaySeconds >= 0) { "delaySeconds must not be negative" }
            val app = context.applicationContext
            val intent = Intent(app, AlarmReceiver::class.java)
                .setAction(ACTION_TRIGGER)
                .putExtra(EXTRA_PULSE_KEY, pulseKey)
                .putExtra(EXTRA_TTL_SECONDS, ttlSeconds)
                .putExtra(EXTRA_PRIORITY, priority.wire)
            val pending = PendingIntent.getBroadcast(
                app,
                pulseKey.hashCode(),
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            val alarms = app.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            val triggerAt = SystemClock.elapsedRealtime() + delaySeconds * 1000L
            val exactAccess = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S &&
                runCatching { alarms.canScheduleExactAlarms() }.getOrDefault(false) &&
                runCatching { ProPulse.requireConfig().enableExactAlarms }.getOrDefault(false)

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                if (exactAccess) {
                    alarms.setExactAndAllowWhileIdle(
                        AlarmManager.ELAPSED_REALTIME_WAKEUP, triggerAt, pending
                    )
                } else {
                    alarms.setAndAllowWhileIdle(
                        AlarmManager.ELAPSED_REALTIME_WAKEUP, triggerAt, pending
                    )
                }
            } else {
                alarms.set(AlarmManager.ELAPSED_REALTIME_WAKEUP, triggerAt, pending)
            }
        }
    }
}
