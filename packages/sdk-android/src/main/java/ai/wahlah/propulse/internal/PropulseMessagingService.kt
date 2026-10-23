// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import ai.wahlah.propulse.ProPulse
import android.content.Context
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.launch
import org.json.JSONArray

/**
 * Optional FCM adapter. The consuming application must configure Firebase for its package.
 * Notifications acknowledge the server run_id and any coalesced run_ids in a data payload.
 */
class PropulseMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        applicationContext.getSharedPreferences(TOKEN_PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(TOKEN_KEY, token)
            .apply()

        if (ProPulse.isStarted()) {
            ProPulse.scope.launch {
                runCatching { ProPulse.client.registerDevice() }
            }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        if (!ProPulse.isStarted()) ProPulse.autoStart(applicationContext)
        if (!ProPulse.isStarted()) return

        val data = message.data
        val notification = message.notification
        val title = notification?.title ?: data["title"] ?: "ProPulse"
        val body = notification?.body ?: data["body"].orEmpty()
        val deeplink = data["deeplink"]
        val urgent = data["priority"] == "urgent"
        val notificationId = data["notification_id"]?.toIntOrNull()
            ?: data["run_id"]?.hashCode()
            ?: message.messageId?.hashCode()
            ?: DEFAULT_NOTIFICATION_ID

        if (body.isNotBlank()) {
            NotificationDispatcher.show(
                context = applicationContext,
                title = title,
                body = body,
                deeplink = deeplink,
                urgent = urgent,
                notificationId = notificationId,
            )
            val speak = data["speak"]?.toBooleanStrictOrNull()
                ?: runCatching { ProPulse.requireConfig().speakByDefault }.getOrDefault(false)
            if (speak) ProPulse.voice.speak(body, urgent)
        }

        val runIds = linkedSetOf<String>()
        data["run_id"]?.takeIf { it.isNotBlank() }?.let(runIds::add)
        data["run_ids"]?.let { encoded ->
            runCatching { JSONArray(encoded) }.getOrNull()?.let { array ->
                for (index in 0 until array.length()) {
                    array.optString(index).takeIf { it.isNotBlank() }?.let(runIds::add)
                }
            }
        }

        ProPulse.scope.launch {
            runCatching { PulseRegistry.flush(applicationContext, ProPulse.client) }
            runIds.forEach { runId ->
                runCatching { ProPulse.client.ack(runId, "push") }
            }
            runCatching { ProPulse.scheduler.scheduleAdaptiveChain() }
        }
    }

    companion object {
        private const val TOKEN_PREFS = "propulse_fcm"
        private const val TOKEN_KEY = "token"
        private const val DEFAULT_NOTIFICATION_ID = 7712
    }
}
