// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import ai.wahlah.propulse.ProPulse
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.PowerManager
import org.json.JSONObject

internal object DeviceState {

    fun current(context: Context): JSONObject = JSONObject().apply {
        put("battery", ProPulse.governor.batteryPercent())
        put("charging", ProPulse.governor.isCharging())
        put("network", networkType(context))
        put("screen_on", screenOn(context))
        put("doze", ProPulse.governor.isDozeMode())
    }

    private fun networkType(context: Context): String {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return "none"
        val caps = cm.getNetworkCapabilities(network) ?: return "none"
        return when {
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            else -> "other"
        }
    }

    private fun screenOn(context: Context): Boolean {
        val power = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        return power.isInteractive
    }
}
