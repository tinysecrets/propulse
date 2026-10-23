// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import android.content.Context

/** The 429 is the conversion event — surface the upgrade link exactly once per day. */
internal object UpgradeNotifier {

    private const val PREFS = "propulse_upgrade"
    private const val LAST_SHOWN = "last_shown"
    private const val COOLDOWN_MS = 86_400_000L

    fun notify(context: Context, url: String) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val last = prefs.getLong(LAST_SHOWN, 0L)
        val now = System.currentTimeMillis()
        if (now - last < COOLDOWN_MS) return

        prefs.edit().putLong(LAST_SHOWN, now).apply()
        NotificationDispatcher.show(
            context = context,
            title = "ProPulse quota reached",
            body = "You have hit the free tier. Upgrade for 50x the pulses.",
            deeplink = url,
            urgent = false,
            notificationId = 7711,
        )
    }
}
