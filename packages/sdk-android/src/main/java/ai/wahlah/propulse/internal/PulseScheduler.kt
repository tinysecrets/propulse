// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import android.content.Context
import ai.wahlah.propulse.ProPulse
import ai.wahlah.propulse.ProPulseConfig
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit
import kotlin.random.Random

/**
 * Adaptive polling. Never setRepeating. Jittered one-shot chain, server-driven cadence.
 * 15-minute floor comes from WorkManager's PeriodicWorkRequest minimum.
 */
internal class PulseScheduler(private val context: Context, private val config: ProPulseConfig) {

    private val workManager get() = WorkManager.getInstance(context)

    private val constraints = Constraints.Builder()
        .setRequiredNetworkType(NetworkType.CONNECTED)
        .build()

    /** Belt-and-braces periodic tick. Cheap, survives process death. */
    fun schedulePeriodic() {
        val request = PeriodicWorkRequestBuilder<PulseWorker>(15, TimeUnit.MINUTES)
            .setConstraints(constraints)
            .addTag(TAG_PERIODIC)
            .build()
        workManager.enqueueUniquePeriodicWork(
            WORK_PERIODIC, ExistingPeriodicWorkPolicy.KEEP, request,
        )
    }

    /** Fine-grained chain, only while the app is warm and battery allows. */
    fun scheduleAdaptiveChain(delaySeconds: Long? = null) {
        val base = delaySeconds ?: config.defaultPollSeconds
        val jittered = if (config.jitter) {
            base + Random.nextLong(0, maxOf(1L, base / 2))
        } else {
            base
        }
        val request = OneTimeWorkRequestBuilder<PulseWorker>()
            .setInitialDelay(jittered, TimeUnit.SECONDS)
            .setConstraints(constraints)
            .addTag(TAG_ADAPTIVE)
            .build()
        workManager.enqueueUniqueWork(WORK_ADAPTIVE, ExistingWorkPolicy.REPLACE, request)
    }

    /** Re-arm from the server's next_poll_in. */
    fun rescheduleFrom(nextPollSeconds: Long) {
        if (ProPulse.governor.shouldCollapseToPushOnly()) {
            schedulePeriodic()
            return
        }
        scheduleAdaptiveChain(config.clampedPoll(nextPollSeconds))
    }

    fun cancelAll() {
        workManager.cancelUniqueWork(WORK_ADAPTIVE)
        workManager.cancelUniqueWork(WORK_PERIODIC)
    }

    companion object {
        const val TAG_PERIODIC = "propulse_periodic"
        const val TAG_ADAPTIVE = "propulse_adaptive"
        const val WORK_PERIODIC = "propulse_periodic_work"
        const val WORK_ADAPTIVE = "propulse_adaptive_work"
    }
}
