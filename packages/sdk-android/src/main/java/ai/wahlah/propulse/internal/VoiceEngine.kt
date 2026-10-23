// SPDX-License-Identifier: Apache-2.0
package ai.wahlah.propulse.internal

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import android.speech.tts.TextToSpeech
import ai.wahlah.propulse.ProPulseConfig
import java.util.Locale

/** On-device TTS by default. Ducks music rather than pausing it. */
internal class VoiceEngine(private val context: Context, private val config: ProPulseConfig) {

    private var tts: TextToSpeech? = null
    @Volatile private var ready = false

    init {
        tts = TextToSpeech(context) { status ->
            ready = status == TextToSpeech.SUCCESS
            if (ready) {
                tts?.language = Locale.getDefault()
                tts?.setSpeechRate(1.0f)
            }
        }
    }

    fun speak(text: String, urgent: Boolean = false) {
        if (!ready || text.isBlank()) return
        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val focus = AudioFocusRequest.Builder(
            if (urgent) AudioManager.AUDIOFOCUS_GAIN_TRANSIENT
            else AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK
        ).apply {
            setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) setOnAudioFocusChangeListener { }
        }.build()

        audioManager.requestAudioFocus(focus)
        val trimmed = text.take(220)
        tts?.speak(trimmed, if (urgent) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD,
            null, "propulse_${System.currentTimeMillis()}")
    }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        ready = false
    }
}
