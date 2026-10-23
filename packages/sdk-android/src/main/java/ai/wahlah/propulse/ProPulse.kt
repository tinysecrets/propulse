// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse

import android.app.Application
import android.content.Context
import ai.wahlah.propulse.internal.BatteryGovernor
import ai.wahlah.propulse.internal.Client
import ai.wahlah.propulse.internal.PulseRegistry
import ai.wahlah.propulse.internal.PulseScheduler
import ai.wahlah.propulse.internal.SigningKey
import ai.wahlah.propulse.internal.VoiceEngine
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Wah-Lah ProPulse AI — two-line integration.
 *
 * ```
 * ProPulse.start(this, "pp_pub_live_xxxx")
 * ProPulse.on("cart_idle").after(15.minutes).say("Still thinking? 10% off.")
 * ```
 *
 * Fails soft: no network, bad key, or missing push all degrade to no-op.
 */
object ProPulse {

    @Volatile private var started = false
    @Volatile private var config: ProPulseConfig? = null

    internal val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    internal lateinit var client: Client
    internal lateinit var scheduler: PulseScheduler
    internal lateinit var voice: VoiceEngine
    internal lateinit var governor: BatteryGovernor

    /** Line 1. Idempotent. Safe to call from Application.onCreate(). */
    @JvmStatic
    @JvmOverloads
    fun start(context: Context, publicKey: String, config: ProPulseConfig = ProPulseConfig()) {
        if (started) return
        synchronized(this) {
            if (started) return
            val app = context.applicationContext
            this.config = config
            SigningKey.ensure(app)
            client = Client(app, publicKey, config)
            scheduler = PulseScheduler(app, config)
            voice = VoiceEngine(app, config)
            governor = BatteryGovernor(app)
            started = true

            scope.launch {
                runCatching { client.registerDevice() }
                runCatching { PulseRegistry.flush(app, client) }
                if (!governor.shouldCollapseToPushOnly()) {
                    scheduler.scheduleAdaptiveChain()
                }
            }
        }
    }

    /** Line 2. Register a trigger and speak when it fires. */
    @JvmStatic
    fun on(triggerKey: String): TriggerBuilder =
        TriggerBuilder(triggerKey, requireConfig())

    /** Fire a trigger immediately (device-side evaluation). */
    @JvmStatic
    @JvmOverloads
    fun trigger(trigger: Trigger, ttlSeconds: Long = 3600L, priority: Priority = Priority.NORMAL) {
        val cfg = requireConfig()
        val ctx = config ?: return
        scope.launch {
            runCatching {
                val ctxApp = appContext()
                PulseRegistry.enqueue(ctxApp, trigger, ttlSeconds, priority)
                client.signal(trigger.key, trigger.toMap(), ttlSeconds, priority)
            }
        }
    }

    /** Suppress voice between local hours. */
    @JvmStatic
    fun quietHours(startHour: Int, endHour: Int) {
        config = requireConfig().copy(quietStartHour = startHour, quietEndHour = endHour)
    }

    /** Battery below this and not charging -> push-only. */
    @JvmStatic
    fun batteryFloor(percent: Int) {
        config = requireConfig().copy(batteryFloorPercent = percent)
    }

    /** Opt out of everything; the app behaves exactly as before. */
    @JvmStatic
    fun stop() {
        if (!started) return
        scheduler.cancelAll()
        started = false
    }

    @JvmStatic fun isStarted(): Boolean = started

    internal fun appContext(): Context = client.context

    internal fun requireConfig(): ProPulseConfig =
        config ?: error("ProPulse.start() must be called before use")

    internal fun autoStart(context: Context) {
        val app = context.applicationContext
        val key = ProPulseInitProvider.readKey(app) ?: return
        start(app, key)
    }
}
