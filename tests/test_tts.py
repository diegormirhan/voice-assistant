from speech.tts import PiperTTS
from pathlib import Path

model_path = Path("models/piper/pt_BR-faber-medium.onnx")

text = "Olá! Este é um teste da classe PiperTTS. A reunião de amanhã foi adiada para a próxima semana."

tts = PiperTTS(model_path)

for audio_bytes, sample_rate in tts.synthesize(text):
    print(f"Chunk: {len(audio_bytes)} bytes @ {sample_rate} Hz")
