from audio.capture import AudioCapture
from audio.vad import SpeechSegmenter

segmenter = SpeechSegmenter(lambda seg: print(f"segment: {len(seg)/16000:.2f}s"))
capture = AudioCapture(segmenter.add)

capture.start()
input("Gravando... Enter para parar!\n")
capture.stop()