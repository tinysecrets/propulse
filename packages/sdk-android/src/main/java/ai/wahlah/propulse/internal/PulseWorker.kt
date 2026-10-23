// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import ai.wahlah.propulse.ProPulse
import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

internal class PulseWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        if (!ProPulse.isStarted()) return@withContext Result.success()

        val config = ProPulse.requireConfig()
        val client = ProPulse.client

        // Flush the encrypted offline outbox first.
        runCatching { PulseRegistry.flush(applicationContext, client) }

        // Ask the server how long to wait next.
        val remote = runCatching { client.fetchConfig() }.getOrNull()
        val nextPoll = remote
            ?.optJSONObject("poll")
            ?.optLong("default_s", config.defaultPollSeconds)
            ?: config.defaultPollSeconds

        if (!ProPulse.governor.shouldCollapseToPushOnly()) {
            ProPulse.scheduler.rescheduleFrom(nextPoll)
        }
        Result.success()
    }
}
