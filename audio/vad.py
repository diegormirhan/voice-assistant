import numpy as np
import onnxruntime as ort

class SpeechSegmenter:
    """Silero VAD + speech buffering.

    For each audio block, decides if it is speech (VAD) and accumulates
    blocks into a segment. Delivers the full segment via on_segment when
    a hangover silence is detected.
    """

    SAMPLE_RATE = 16000
    CONTEXT_SIZE = 64
    VAD_THRESHOLD = 0.5     # speech probability cutoff
    MIN_SPEECH_MS = 250     # ignore segments shorter than this
    HANGOVER_MS = 1000       # silence after speech before closing segment

    def __init__(self, on_segment, on_speech_start=None):
        """on_segment: callback receiving np.ndarray int16 (full speech).
        on_speech_start: callback fired the moment speech is detected (barge-in)"""
        self._on_segment = on_segment
        self._on_speech_start = on_speech_start

        # buffer state
        self._buffer = []
        self._speaking = False
        self._silence_ms = 0
        self._speech_ms = 0

        # silero VAD stateful session
        self._session = ort.InferenceSession("models/vad/silero_vad.onnx")
        self._input_name = self._session.get_inputs()[0].name
        self._state_name = self._session.get_inputs()[1].name
        self._sr_name = self._session.get_inputs()[2].name
        self._context = np.zeros((1, self.CONTEXT_SIZE), dtype=np.float32)
        self._state = np.zeros((2, 1, 128), dtype=np.float32)

    def add(self, block: np.ndarray):
        """Called by the capture for each 32ms block."""
        prob = self._vad_prob(block)
        block_ms = len(block) / self.SAMPLE_RATE * 1000

        if prob >= self.VAD_THRESHOLD:
            if not self._speaking and self._on_speech_start:
                self._on_speech_start()
            self._speaking = True
            self._speech_ms += block_ms
            self._silence_ms = 0
            self._buffer.append(block)
        elif self._speaking:
            self._silence_ms += block_ms
            self._buffer.append(block)
            if self._silence_ms >= self.HANGOVER_MS:
                self._close()

    def _vad_prob(self, block: np.ndarray) -> float:
        x = block.astype(np.float32) / 32768.0
        x = x.reshape(1, -1)
        inp = np.concatenate([self._context, x], axis=1)
        out, new_state = self._session.run(
            None,
            {self._input_name: inp, self._state_name: self._state,
             self._sr_name: np.array(self.SAMPLE_RATE, dtype=np.int64)},
        )
        self._state = np.asarray(new_state)
        self._context = inp[:, -self.CONTEXT_SIZE:]
        return float(np.asarray(out).squeeze())

    def _close(self):
        if self._speech_ms >= self.MIN_SPEECH_MS and self._buffer:
            self._on_segment(np.concatenate(self._buffer))
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, self.CONTEXT_SIZE), dtype=np.float32)
        self._buffer = []
        self._speaking = False
        self._silence_ms = 0
        self._speech_ms = 0