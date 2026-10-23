// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import ai.wahlah.propulse.ProPulse
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.PowerManager

/**
 * Battery-first policy. Below the floor and unplugged -> push-only.
 * Above 50% or charging -> realtime channel permitted.
 */
internal class BatteryGovernor(private val context: Context) {

    private val power: PowerManager
        get() = context.getSystemService(Context.POWER_SERVICE) as PowerManager

    fun batteryPercent(): Int {
        val intent = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            ?: return 100
        val level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, 100)
        return if (level < 0 || scale <= 0) 100 else (level * 100) / scale
    }

    fun isCharging(): Boolean {
        val intent = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            ?: return false
        val status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
        return status == BatteryManager.BATTERY_STATUS_CHARGING ||
            status == BatteryManager.BATTERY_STATUS_FULL
    }

    fun isDozeMode(): Boolean = power.isDeviceIdleMode

    fun shouldCollapseToPushOnly(): Boolean {
        val config = runCatching { ProPulse.requireConfig() }.getOrNull() ?: return false
        if (isCharging()) return false
        if (isDozeMode()) return true
        return batteryPercent() < config.batteryFloorPercent
    }

    fun canUseRealtime(): Boolean {
        if (!runCatching { ProPulse.requireConfig().enableRealtimeChannel }.getOrDefault(false)) {
            return false
        }
        if (isCharging()) return true
        return batteryPercent() > 50 && !isDozeMode()
    }
}
