// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse

sealed class Trigger(val key: String, val kind: String) {

    abstract fun toMap(): Map<String, Any?>

    class Time(key: String, val everySeconds: Long? = null, val atEpochMs: Long? = null) :
        Trigger(key, "time") {
        override fun toMap() = buildMap<String, Any?> {
            put("kind", "time")
            everySeconds?.let { put("every_seconds", it) }
            atEpochMs?.let { put("at", it / 1000.0) }
        }
    }

    class Signal(key: String, val threshold: Int = 1) : Trigger(key, "signal") {
        override fun toMap() = mapOf("kind" to "signal", "key" to key, "threshold" to threshold)
    }

    class DeviceState(
        key: String,
        val batteryBelow: Int? = null,
        val charging: Boolean? = null,
        val network: String = "any",
    ) : Trigger(key, "device_state") {
        override fun toMap() = buildMap<String, Any?> {
            put("kind", "device_state")
            batteryBelow?.let { put("battery_below", it) }
            charging?.let { put("charging", it) }
            put("network", network)
        }
    }

    class Compound(key: String, val op: String, val n: Int, val windowSeconds: Int) :
        Trigger(key, "compound") {
        override fun toMap() = mapOf(
            "kind" to "compound", "op" to op, "n" to n,
            "window_seconds" to windowSeconds,
        )
    }
}

class TriggerBuilder(private val key: String, private val config: ProPulseConfig) {

    private var everySeconds: Long? = null
    private var ttlSeconds: Long = 3600L
    private var priority: Priority = Priority.NORMAL
    private var text: String? = null
    private var deeplink: String? = null
    private var speak: Boolean = config.speakByDefault

    fun after(seconds: Long): TriggerBuilder = apply { everySeconds = seconds }
    fun ttl(seconds: Long): TriggerBuilder = apply { ttlSeconds = seconds }
    fun priority(p: Priority): TriggerBuilder = apply { priority = p }
    fun silent(): TriggerBuilder = apply { speak = false }
    fun open(uri: String): TriggerBuilder = apply { deeplink = uri }

    /** Terminal call — registers and, when speak is on, utters [utterance]. */
    fun say(utterance: String) {
        text = utterance
        register()
    }

    /** Terminal call without speech. */
    fun register() {
        val ctx = ProPulse.appContext()
        val trigger = if (everySeconds != null) {
            Trigger.Time(key, everySeconds = everySeconds)
        } else {
            Trigger.Signal(key)
        }
        PulseRegistry.save(ctx, RegisteredPulse(
            key = key, kind = trigger.kind, ttlSeconds = ttlSeconds,
            priority = priority.wire, text = text, deeplink = deeplink, speak = speak,
            everySeconds = everySeconds,
        ))
        ProPulse.trigger(trigger, ttlSeconds, priority)
    }
}
