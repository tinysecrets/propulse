// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse

import java.util.concurrent.TimeUnit

data class ProPulseConfig(
    val baseUrl: String = "https://api.propulse.wah-lah.com",
    val defaultPollSeconds: Long = 300L,
    val minPollSeconds: Long = 60L,
    val maxPollSeconds: Long = 900L,
    val jitter: Boolean = true,
    val quietStartHour: Int? = 23,
    val quietEndHour: Int? = 7,
    val batteryFloorPercent: Int = 15,
    val enableRealtimeChannel: Boolean = true,
    val enableExactAlarms: Boolean = true,
    val speakByDefault: Boolean = true,
    val notificationChannelId: String = "propulse_default",
    val urgentChannelId: String = "propulse_urgent",
    val requestNotificationPermission: Boolean = true,
    val logLevel: LogLevel = LogLevel.WARN,
) {
    enum class LogLevel { NONE, ERROR, WARN, INFO, DEBUG }

    init {
        require(defaultPollSeconds in minPollSeconds..maxPollSeconds) {
            "defaultPollSeconds must be within [min, max]"
        }
    }

    fun clampedPoll(seconds: Long): Long =
        seconds.coerceIn(minPollSeconds, maxPollSeconds)
}

enum class Priority(val wire: String, val pollSeconds: Long) {
    URGENT("urgent", 60L),
    HIGH("high", 120L),
    NORMAL("normal", 300L),
    LOW("low", 900L),
}

fun Int.minutes(): Long = TimeUnit.MINUTES.toSeconds(this.toLong())
fun Int.hours(): Long = TimeUnit.HOURS.toSeconds(this.toLong())
