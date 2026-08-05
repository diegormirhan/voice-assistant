import asyncio, threading, queue
import numpy as np
from speech.stt import WhisperSTT
from audio.vad import SpeechSegmenter
from audio.capture import AudioCapture

def main():
    stt = WhisperSTT()
    segment_queue = queue.Queue()

    def on_segment(seg: np.ndarray):
        segment_queue.put(seg) # só infileira, nao bloqueia

    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()

    async def consume_segments():
        while True:
            seg = await asyncio.to_thread(segment_queue.get)
            text = await stt.transcribe(seg.tobytes())
            print(f"transcrito: {text!r}")

    # agenda o consumidor no loop
    asyncio.run_coroutine_threadsafe(consume_segments(), loop)

    segmenter = SpeechSegmenter(on_segment)
    capture = AudioCapture(segmenter.add)

    capture.start()
    input("fale... Enter para sair.")
    capture.stop()

main()