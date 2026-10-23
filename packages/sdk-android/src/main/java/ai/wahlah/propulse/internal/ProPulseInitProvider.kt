// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import android.content.ContentProvider
import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.net.Uri
import ai.wahlah.propulse.ProPulse

/**
 * Auto-init. Lets the two-line promise work from any Context without the app
 * wiring Application.onCreate().
 */
class ProPulseInitProvider : ContentProvider() {

    override fun onCreate(): Boolean {
        val ctx = context ?: return true
        NotificationDispatcher.ensureChannels(ctx)
        ProPulse.autoStart(ctx)
        return true
    }

    override fun query(uri: Uri, projection: Array<out String>?, selection: String?,
                       selectionArgs: Array<out String>?, sortOrder: String?): Cursor? = null

    override fun getType(uri: Uri): String? = null

    override fun insert(uri: Uri, values: ContentValues?): Uri? = null

    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0

    override fun update(uri: Uri, values: ContentValues?, selection: String?,
                        selectionArgs: Array<out String>?): Int = 0

    companion object {
        private const val META_KEY = "ai.wahlah.propulse.PUBLIC_KEY"

        fun readKey(context: Context): String? = runCatching {
            val info = context.packageManager.getApplicationInfo(
                context.packageName,
                android.content.pm.PackageManager.GET_META_DATA,
            )
            info.metaData?.getString(META_KEY)
        }.getOrNull()
    }
}
