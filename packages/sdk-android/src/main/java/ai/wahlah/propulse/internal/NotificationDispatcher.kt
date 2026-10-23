// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

internal object NotificationDispatcher {

    private const val DEFAULT_ID = "propulse_default"
    private const val URGENT_ID = "propulse_urgent"

    fun ensureChannels(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(DEFAULT_ID, "ProPulse", NotificationManager.IMPORTANCE_DEFAULT)
        )
        manager.createNotificationChannel(
            NotificationChannel(URGENT_ID, "ProPulse Urgent", NotificationManager.IMPORTANCE_HIGH)
        )
    }

    fun show(context: Context, title: String, body: String, deeplink: String?,
             urgent: Boolean, notificationId: Int) {
        ensureChannels(context)
        val channel = if (urgent) URGENT_ID else DEFAULT_ID

        val intent = deeplink?.let {
            Intent(Intent.ACTION_VIEW, Uri.parse(it)).apply {
                setPackage(context.packageName)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
        } ?: context.packageManager.getLaunchIntentForPackage(context.packageName)

        val pending = intent?.let {
            PendingIntent.getActivity(
                context, notificationId, it,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        }

        val notification = NotificationCompat.Builder(context, channel)
            .setSmallIcon(android.R.drawable.ic_popup_reminder)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(if (urgent) NotificationCompat.PRIORITY_HIGH else NotificationCompat.PRIORITY_DEFAULT)
            .setAutoCancel(true)
            .apply { pending?.let { setContentIntent(it) } }
            .build()

        runCatching {
            NotificationManagerCompat.from(context).notify(notificationId, notification)
        }
    }
}
