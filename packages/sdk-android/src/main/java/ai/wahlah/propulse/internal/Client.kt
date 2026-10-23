// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import android.content.Context
import android.os.Build
import ai.wahlah.propulse.Priority
import ai.wahlah.propulse.ProPulseConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

internal class Client(
    val context: Context,
    private val publicKey: String,
    private val config: ProPulseConfig,
) {
    private val http = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .callTimeout(20, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private val jsonType = "application/json; charset=utf-8".toMediaType()

    suspend fun registerDevice(): Boolean = withContext(Dispatchers.IO) {
        val body = JSONObject().apply {
            put("install_id", SigningKey.installId())
            put("platform", "android")
            put("app_version", appVersion())
            put("sdk_version", BUILD_VERSION)
            put(
                "push_token",
                context.getSharedPreferences("propulse_fcm", Context.MODE_PRIVATE)
                    .getString("token", "").orEmpty(),
            )
            put("locale", java.util.Locale.getDefault().toString())
            put("timezone", java.util.TimeZone.getDefault().id)
        }.toString()

        val request = signed("POST", "/v1/devices/register", body)
        runCatching {
            http.newCall(request).execute().use { it.isSuccessful }
        }.getOrDefault(false)
    }

    suspend fun signal(
        pulseKey: String,
        trigger: Map<String, Any?>,
        ttlSeconds: Long,
        priority: Priority,
    ): Boolean = withContext(Dispatchers.IO) {
        val body = JSONObject().apply {
            put("pulse", pulseKey)
            put("install_id", SigningKey.installId())
            put("trigger", JSONObject(trigger))
            put("device_state", DeviceState.current(context))
            put("client_ts", System.currentTimeMillis() / 1000.0)
        }.toString()

        val request = signed("POST", "/v1/pulses:signal", body)
        runCatching {
            http.newCall(request).execute().use { resp ->
                if (resp.code == 429) {
                    resp.header("x-pp-upgrade-url")?.let { UpgradeNotifier.notify(context, it) }
                }
                resp.isSuccessful
            }
        }.getOrDefault(false)
    }

    suspend fun ack(runId: String, channel: String): Boolean = withContext(Dispatchers.IO) {
        val body = JSONObject().apply {
            put("run_id", runId)
            put("delivered_at", System.currentTimeMillis() / 1000.0)
            put("channel", channel)
        }.toString()
        runCatching {
            http.newCall(signed("POST", "/v1/pulses/ack", body)).execute().use { it.isSuccessful }
        }.getOrDefault(false)
    }

    suspend fun fetchConfig(): JSONObject? = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url(config.baseUrl + "/v1/config")
            .header("x-pp-key", publicKey)
            .header("x-pp-protocol", PROTOCOL_VERSION.toString())
            .get()
            .build()
        runCatching {
            http.newCall(request).execute().use { resp ->
                if (resp.isSuccessful) JSONObject(resp.body?.string() ?: "{}") else null
            }
        }.getOrNull()
    }

    private fun signed(method: String, path: String, body: String): Request {
        val ts = (System.currentTimeMillis() / 1000).toString()
        val nonce = randomNonce()
        val signature = hmac(ts, nonce, body)

        return Request.Builder()
            .url(config.baseUrl + path)
            .header("x-pp-key", publicKey)
            .header("x-pp-ts", ts)
            .header("x-pp-nonce", nonce)
            .header("x-pp-sig", signature)
            .header("x-pp-protocol", PROTOCOL_VERSION.toString())
            .header("content-type", "application/json")
            .header("idempotency-key", "$path:$ts:$nonce".hashCode().toString())
            .method(method, body.toRequestBody(jsonType))
            .build()
    }

    private fun hmac(ts: String, nonce: String, body: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
            .digest(body.toByteArray()).joinToString("") { "%02x".format(it) }
        val message = "$ts.$nonce.$digest"
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(SigningKey.secret().toByteArray(), "HmacSHA256"))
        return android.util.Base64.encodeToString(
            mac.doFinal(message.toByteArray()),
            android.util.Base64.NO_WRAP,
        )
    }

    private fun randomNonce(): String {
        val bytes = ByteArray(16).also { java.security.SecureRandom().nextBytes(it) }
        return android.util.Base64.encodeToString(
            bytes, android.util.Base64.URL_SAFE or android.util.Base64.NO_WRAP or
                android.util.Base64.NO_PADDING,
        )
    }

    @Suppress("DEPRECATION")
    private fun appVersion(): String = runCatching {
        context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: "0"
    }.getOrDefault("0")

    companion object {
        const val PROTOCOL_VERSION = 3
        const val BUILD_VERSION = "1.0.0"
    }
}
