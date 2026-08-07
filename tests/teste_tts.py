# teste_tts.py
from kokoro_onnx import Kokoro
import soundfile as sf

kokoro = Kokoro("models/kokoro-onnx/kokoro-v1.0.onnx", "models/kokoro-onnx/voices-v1.0.bin")
samples, sample_rate = kokoro.create(
    "Ola, tudo bem? Como posso ajudar voce hoje?",
    voice="pf_dora",      # voz feminina pt-BR
    speed=1.0,
    lang="pt-br",
)
sf.write("teste_kokoro.wav", samples, sample_rate)
print("gerado teste_kokoro.wav")