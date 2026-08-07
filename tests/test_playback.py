import threading, time
from pathlib import Path

from audio.playback import AudioPlayback
from audio.capture import AudioCapture
from audio.vad import SpeechSegmenter
from speech.tts import PiperTTS

model_path = Path("models/piper/pt_BR-faber-medium.onnx")
text = "Esta é uma frase longa para testar o playback. Preciso de áudio suficiente para verificar a interrupção."

tts = PiperTTS(model_path)
playback = AudioPlayback(tts.sample_rate)
interrupt = threading.Event()

segmenter = SpeechSegmenter(
    on_segment=lambda seg: None,
    on_speech_start=interrupt.set
)

print("[test] iniciando playback")
start = time.time()
capture = AudioCapture(on_audio=segmenter.add)

capture.start()
playback.start()

playback.play(tts.synthesize(text), interrupt)
print(f"[test] playback terminou em {time.time() - start:.2f}s")

capture.stop()
playback.stop()




