// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import android.content.Context
import android.util.Base64
import java.security.SecureRandom

/** Per-install HMAC secret in EncryptedSharedPreferences. */
internal object SigningKey {

    private const val PREF = "propulse_secure"
    private const val KEY = "pp_signing_secret"
    private const val INSTALL = "pp_install_id"

    @Volatile private var cached: String? = null
    @Volatile private var cachedInstall: String? = null

    fun ensure(context: Context) {
        if (cached != null && cachedInstall != null) return
        synchronized(this) {
            if (cached == null) cached = readOrCreate(context, KEY, 32)
            if (cachedInstall == null) cachedInstall = readOrCreate(context, INSTALL, 16)
        }
    }

    fun secret(): String = cached ?: error("SigningKey.ensure() not called")
    fun installId(): String = cachedInstall ?: error("SigningKey.ensure() not called")

    private fun readOrCreate(context: Context, name: String, bytes: Int): String {
        val prefs = context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
        prefs.getString(name, null)?.let { return it }
        val random = ByteArray(bytes).also { SecureRandom().nextBytes(it) }
        val value = Base64.encodeToString(
            random, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING,
        )
        prefs.edit().putString(name, value).apply()
        return value
    }
}
