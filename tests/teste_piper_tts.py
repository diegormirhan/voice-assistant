import time, wave
import sounddevice as sd
from piper import PiperVoice

# Texto de teste
text1 = "Não se preocupe, está tudo bem. A reunião de amanhã foi adiada para a próxima semana, então você pode ir à academia sem pressa. Está tudo bem com você hoje?"
text2 = "O voo AZ 2847 sai às 14h30 do terminal 3. O custo total foi de R$ 1.250,00, incluindo 15kg de bagagem."
text3 = "A médica receitou um antibiótico para a infecção. O diagnóstico foi rápido, graças à experiência da profissional. O result vai ser melhor se você clicar em start no modelo onnx."

# Download da voz pt_BR
voice_name = "pt_BR-faber-medium"
# pt_BR-cadu-medium
# pt_BR-faber-medium

# Carregar modelo
voice = PiperVoice.load(f"models/piper/{voice_name}.onnx")

# Teste 1: Síntese completa (baseline)
print("=== Teste 1: Síntese completa ===")
start = time.time()
with wave.open("results/piper_full.wav", "wb") as wav_file:
    voice.synthesize_wav(text1, wav_file)
full_latency = time.time() - start
print(f"Latência completa: {full_latency:.3f}s")

# Teste 2: Streaming com chunks
print("\n=== Teste 2: Streaming ===")
start = time.time()
first_chunk_time = None
chunk_count = 0
sample_rate = None

for chunk in voice.synthesize(text1):
    if first_chunk_time is None:
        first_chunk_time = time.time() - start
        print(f"TTFA (Time To First Audio): {first_chunk_time:.3f}s")
        
    # Aqui você tocaria o chunk via sounddevice
    # sd.play(chunk.audio_int16_bytes, samplerate=chunk.sample_rate)
    sample_rate = chunk.sample_rate
    chunk_count += 1

total_time = time.time() - start
print(f"Chunks gerados: {chunk_count}")
print(f"Tempo total: {total_time:.3f}s")
print(f"Sample rate: {sample_rate} Hz")