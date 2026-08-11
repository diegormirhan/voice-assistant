import asyncio
from pathlib import Path

from audio.capture import AudioCapture
from audio.playback import AudioPlayback
from audio.vad import SpeechSegmenter
from speech.llm import LlamaClient
from speech.sentence_buffer import SentenceBuffer
from speech.tts import PiperTTS

model_path = Path("models/piper/pt_BR-faber-medium.onnx")

async def run():
    tts = PiperTTS(model_path)
    playback = AudioPlayback(tts.sample_rate)

    # Barge-in real: falar durante o playback interrompe a resposta.
    segmenter = SpeechSegmenter(
        on_segment=lambda seg: None,
        on_speech_start=playback.interrupt,
    )
    capture = AudioCapture(on_audio=segmenter.add)

    llm = LlamaClient()
    buffer = SentenceBuffer()

    capture.start()
    playback.start()

    async for token in llm.stream("Conte uma piada curta em portugues."):
        if playback.interrupted:
            print("[test] interrompido pelo usuario, parando LLM")
            break
        sentence = buffer.add(token)
        if sentence:
            print(f"[tts] {sentence}")
            playback.speak(tts.synthesize(sentence))

    # flush do buffer restante (frase incompleta no final da stream)
    rest = buffer.flush()
    if rest:
        print(f"[tts] {rest}")
        playback.speak(tts.synthesize(rest))

    # aguarda o áudio restante terminar antes de fechar
    playback.wait_until_idle(15)
    capture.stop()
    playback.stop()
    await llm.close()


asyncio.run(run())