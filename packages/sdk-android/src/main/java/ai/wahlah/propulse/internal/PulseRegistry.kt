// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

internal data class RegisteredPulse(
    val key: String,
    val kind: String,
    val ttlSeconds: Long,
    val priority: String,
    val text: String?,
    val deeplink: String?,
    val speak: Boolean,
    val everySeconds: Long?,
)

/** Persistent registry + encrypted offline outbox. */
internal object PulseRegistry {

    private const val PREFS = "propulse_registry"
    private const val KEY_PULSES = "pulses"
    private const val KEY_OUTBOX = "outbox"

    fun save(context: Context, pulse: RegisteredPulse) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val array = runCatching {
            JSONArray(prefs.getString(KEY_PULSES, "[]"))
        }.getOrDefault(JSONArray())

        val filtered = JSONArray()
        for (i in 0 until array.length()) {
            val obj = array.optJSONObject(i) ?: continue
            if (obj.optString("key") != pulse.key) filtered.put(obj)
        }
        filtered.put(pulse.toJson())
        prefs.edit().putString(KEY_PULSES, filtered.toString()).apply()
    }

    fun enqueue(context: Context, trigger: ai.wahlah.propulse.Trigger, ttl: Long, priority: ai.wahlah.propulse.Priority) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val array = runCatching { JSONArray(prefs.getString(KEY_OUTBOX, "[]")) }
            .getOrDefault(JSONArray())
        array.put(JSONObject().apply {
            put("pulse", trigger.key)
            put("trigger", JSONObject(trigger.toMap()))
            put("ttl", ttl)
            put("priority", priority.wire)
            put("at", System.currentTimeMillis())
        })
        prefs.edit().putString(KEY_OUTBOX, array.toString()).apply()
    }

    suspend fun flush(context: Context, client: Client) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val array = runCatching { JSONArray(prefs.getString(KEY_OUTBOX, "[]")) }
            .getOrDefault(JSONArray())
        if (array.length() == 0) return

        val remaining = JSONArray()
        for (i in 0 until array.length()) {
            val obj = array.optJSONObject(i) ?: continue
            val triggerMap = jsonToMap(obj.optJSONObject("trigger"))
            val ok = client.signal(
                obj.optString("pulse"), triggerMap, obj.optLong("ttl", 3600),
                ai.wahlah.propulse.Priority.entries.firstOrNull {
                    it.wire == obj.optString("priority")
                } ?: ai.wahlah.propulse.Priority.NORMAL,
            )
            if (!ok) remaining.put(obj)
        }
        prefs.edit().putString(KEY_OUTBOX, remaining.toString()).apply()
    }

    private fun jsonToMap(obj: JSONObject?): Map<String, Any?> {
        if (obj == null) return emptyMap()
        val map = mutableMapOf<String, Any?>()
        obj.keys().forEach { key -> map[key] = obj.opt(key) }
        return map
    }

    private fun RegisteredPulse.toJson() = JSONObject().apply {
        put("key", key)
        put("kind", kind)
        put("ttl", ttlSeconds)
        put("priority", priority)
        put("text", text)
        put("deeplink", deeplink)
        put("speak", speak)
        everySeconds?.let { put("every_seconds", it) }
    }
}
