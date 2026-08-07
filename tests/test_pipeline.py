import threading
from pathlib import Path

from audio.playback import AudioPlayback
from audio.vad import SpeechSegmenter
from speech.sentence_buffer import SentenceBuffer
from speech.tts import PiperTTS
from audio.capture import AudioCapture

model_path = Path("models/piper/pt_BR-faber-medium.onnx")

# tokens simulados como o llama-server enviaria
tokens = ["Olá", "!", " Como", " você", " está", "?", " Eu", " sou", " um", " assistente", "."]

tts = PiperTTS(model_path)
playback = AudioPlayback(tts.sample_rate)
interrupt = threading.Event()

segmenter = SpeechSegmenter(
    on_segment=lambda seg: None,
    on_speech_start=interrupt.set,
)
capture = AudioCapture(on_audio=segmenter.add)

buffer = SentenceBuffer()
capture.start()

for token in tokens:
    if interrupt.is_set():
        break
    sentence = buffer.add(token)
    if sentence:
        print(f"[tts] {sentence}")
        playback.play(tts.synthesize(sentence), interrupt)

capture.stop()
print("Pipeline Completa")