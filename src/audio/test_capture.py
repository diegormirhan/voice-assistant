# Day 1: Audio capture with Silero VAD (ONNX) + desktop screenshot on speech start
# Pipeline position: first stage (mic -> VAD-segmented audio + screenshot -> STT)

import queue
import threading
from typing import Optional

import numpy as np
import sounddevice as sd
import torch
from silero_vad import load_silero_vad
from mss import MSS
import mss.tools


# Audio stream configuration: 16kHz mono int16, 512 samples per block (32ms)
SAMPLE_RATE = 16000
BLOCKSIZE = 512
CHANNELS = 1
DTYPE = np.int16

# VAD state machine tuning (all values in frames at 32ms each)
VAD_THRESHOLD = 0.5  # speech probability cutoff
TRIGGER_FRAMES = 5  # ~160ms of continuous speech to open a segment
HANGOVER_FRAMES = 15  # ~480ms of silence to close a segment
PRE_TRIGGER_FRAMES = 10  # ~320ms ring buffer to avoid clipping the first phoneme
MIN_SPEECH_SAMPLES = int(SAMPLE_RATE * 0.25)  # discard segments shorter than 250ms


class AudioCapture:
    # Captures audio from the default input device, runs Silero VAD, segments
    # speech, captures a desktop screenshot on speech_start, and pushes the
    # audio segment to output_queue when the segment closes.
    def __init__(
        self,
        output_queue: "queue.Queue[np.ndarray]",
        stop_event: threading.Event,
    ) -> None:
        # Queue that receives finished audio segments (np.ndarray int16, 16kHz)
        self.output_queue = output_queue
        # Set by the orchestrator to request graceful shutdown
        self.stop_event = stop_event

        # Load Silero VAD ONNX model (inference runs via onnxruntime on CPU).
        # The silero-vad pip package bundles the ONNX model; force_onnx_cpu=True
        # pins inference to the CPU provider (we don't need GPU for a 2MB model).
        self._model = load_silero_vad(onnx=True, force_onnx_cpu=True)

        # --- VAD state machine ---
        self._is_speech = False  # True while we are inside a speech segment
        self._trigger_count = 0  # consecutive pre-trigger speech frames
        self._speech_buffer: list[np.ndarray] = []  # chunks of the active segment
        self._ring_buffer: list[np.ndarray] = []  # last N frames for pre-trigger padding
        self._speech_frames = 0  # frames accumulated in the current segment
        self._silence_frames = 0  # consecutive silence frames (hangover counter)

        # Latest screenshot captured at the most recent speech_start.
        # Read by the orchestrator and attached to the next LLM turn.
        self._latest_screenshot: Optional[bytes] = None
        self._screenshot_lock = threading.Lock()  # protects _latest_screenshot
        self._mss = MSS()  # mss is a fast C-backed screen capture library

        self._stream: Optional[sd.InputStream] = None
        self._on_speech_start_cb: Optional[callable] = None

    def _capture_screenshot(self) -> bytes:
        # Grab the primary monitor (index 1; index 0 is the "all monitors"
        # virtual surface) and return PNG bytes via the built-in mss helper.
        monitor = self._mss.monitors[1]
        shot = self._mss.grab(monitor)
        rgb: bytes = shot.rgb  # type: ignore[assignment]
        return mss.tools.to_png(rgb, shot.size)

    def _start_speech(self) -> None:
        # Transition IDLE -> SPEAKING. Prepends the ring buffer to the segment
        # so the first phoneme isn't clipped, then captures a screenshot and
        # fires the user-provided callback.
        self._is_speech = True
        self._speech_frames = 1
        self._silence_frames = 0
        # Ring buffer already contains the last PRE_TRIGGER_FRAMES frames
        # (including the current one), so the segment starts ~320ms in the past.
        self._speech_buffer = list(self._ring_buffer)

        # Screenshot is stored thread-safely; the orchestrator will pick it up
        # when it processes the next transcript.
        with self._screenshot_lock:
            self._latest_screenshot = self._capture_screenshot()

        if self._on_speech_start_cb is not None:
            self._on_speech_start_cb()

    def _end_speech(self) -> None:
        # Transition SPEAKING -> IDLE. Emits the accumulated segment to the
        # output queue (if long enough), then resets all state and the VAD
        # internal LSTM/GRU state.
        total_samples = sum(len(chunk) for chunk in self._speech_buffer)
        if total_samples >= MIN_SPEECH_SAMPLES:
            segment = np.concatenate(self._speech_buffer)
            try:
                self.output_queue.put_nowait(segment)
            except queue.Full:
                pass
        # Reset Silero's internal hidden state so the next segment starts fresh
        self._model.reset_states()
        self._is_speech = False
        self._trigger_count = 0
        self._speech_buffer = []
        self._speech_frames = 0
        self._silence_frames = 0

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info, status: sd.CallbackFlags
    ) -> None:
        # sounddevice callback: runs in a PortAudio-managed thread, must be
        # non-blocking. Called every BLOCKSIZE samples (32ms).
        if self.stop_event.is_set():
            # Cooperative shutdown: raising CallbackStop tells sounddevice to
            # stop invoking this callback.
            raise sd.CallbackStop

        # Convert (frames, channels) to 1-D mono int16 for downstream use.
        frame = indata[:, 0].copy()

        # Always update the ring buffer so the segment start is preserved
        # even when we are currently idle.
        self._ring_buffer.append(frame)
        if len(self._ring_buffer) > PRE_TRIGGER_FRAMES:
            self._ring_buffer.pop(0)

        # Run VAD inference: int16 PCM -> float32 [-1, 1] -> torch tensor.
        # Silero's wrapper returns the speech probability in [0, 1].
        frame_tensor = torch.from_numpy(frame.astype(np.float32) / 32768.0)
        prob = self._model(frame_tensor, SAMPLE_RATE).item()

        if not self._is_speech:
            # IDLE: count consecutive positive frames; only open the segment
            # once we hit TRIGGER_FRAMES. A negative frame resets the count.
            if prob >= VAD_THRESHOLD:
                self._trigger_count += 1
                if self._trigger_count >= TRIGGER_FRAMES:
                    self._start_speech()
            else:
                self._trigger_count = 0
        else:
            # SPEAKING: keep appending frames. Speech frames clear the
            # hangover; silence frames increment it until the segment closes.
            if prob >= VAD_THRESHOLD:
                self._speech_buffer.append(frame)
                self._speech_frames += 1
                self._silence_frames = 0
            else:
                self._speech_buffer.append(frame)
                self._silence_frames += 1
                if self._silence_frames >= HANGOVER_FRAMES:
                    self._end_speech()

    def set_on_speech_start(self, cb: callable) -> None:
        # Register an optional callback fired at every speech_start (useful for
        # barge-in detection by the InterruptionManager).
        self._on_speech_start_cb = cb

    def get_latest_screenshot(self) -> Optional[bytes]:
        # Thread-safe read of the latest screenshot taken at speech_start.
        with self._screenshot_lock:
            return self._latest_screenshot

    def clear_screenshot(self) -> None:
        # Clears the screenshot after the orchestrator has consumed it.
        with self._screenshot_lock:
            self._latest_screenshot = None

    def start(self) -> None:
        # Open the input stream. If the default device fails, fall back to the
        # first available input device so the app still works without config.
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BLOCKSIZE,
                channels=CHANNELS,
                dtype="int16",
                callback=self._audio_callback,
            )
            self._stream.start()
        except sd.PortAudioError:
            input_devices = [
                d for d in sd.query_devices() if d["max_input_channels"] > 0
            ]
            if not input_devices:
                raise RuntimeError("no input device found")
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BLOCKSIZE,
                channels=CHANNELS,
                dtype="int16",
                callback=self._audio_callback,
                device=input_devices[0]["name"],
            )
            self._stream.start()

    def stop(self) -> None:
        # Cooperative shutdown: signal stop, flush the current segment,
        # close the stream and the screen-capture handle.
        self.stop_event.set()
        if self._is_speech:
            self._end_speech()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._mss.close()

    @property
    def is_speech_active(self) -> bool:
        # True while we are inside a speech segment (between start and end).
        return self._is_speech


if __name__ == "__main__":
    # Manual smoke test: speak into the mic and watch segments appear.
    # Ctrl+C to exit cleanly.
    import signal

    q: "queue.Queue[np.ndarray]" = queue.Queue()
    stop = threading.Event()
    capture = AudioCapture(q, stop)

    capture.set_on_speech_start(lambda: print("  [speech_start] screenshot"))
    capture.start()
    print("Listening... (Ctrl+C to stop)\n")

    def _stop_handler(sig, frame):
        print("\nstopping...")
        stop.set()

    signal.signal(signal.SIGINT, _stop_handler)

    try:
        while not stop.is_set():
            try:
                segment = q.get(timeout=0.2)
                duration_s = len(segment) / SAMPLE_RATE
                print(f"  segment: {duration_s:.2f}s ({len(segment)} samples)")
            except queue.Empty:
                pass
    finally:
        capture.stop()
        print("Stopped.")
