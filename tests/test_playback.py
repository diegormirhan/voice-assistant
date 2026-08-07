import threading, time
from pathlib import Path

from audio.playback import AudioPlayback
from audio.capture import AudioCapture
from audio.vad import SpeechSegmenter
from speech.tts import PiperTTS

model_path = Path("models/piper/pt_BR-faber-medium.onnx")
text = "Esta é uma frase longa para testar o playback. Preciso de áudio suficiente para verificar a interrupção. Fale alguma coisa para me interromper."

tts = PiperTTS(model_path)
playback = AudioPlayback(tts.sample_rate)

# Quando o VAD detectar fala, interrompe o playback (barge-in real).
segmenter = SpeechSegmenter(
    on_segment=lambda seg: None,
    on_speech_start=playback.interrupt,
)

capture = AudioCapture(on_audio=segmenter.add)
capture.start()
playback.start()

print("[test] iniciando playback. FALE ALGO para interromper.")
start = time.time()

playback.speak(tts.synthesize(text))

# Aguarda o áudio terminar (ou ser interrompido pela voz).
playback.wait_until_idle(15)
if playback.interrupted:
    print(f"[test] interrompido pela voz em {time.time() - start:.2f}s")
else:
    print("[test] áudio terminou sem interrupção")

capture.stop()
playback.stop()
