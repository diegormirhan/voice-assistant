import queue, threading, torch
from pathlib import Path
from typing import Optional
from mss import MSS
from silero_vad import load_silero_vad
import numpy as np
import sounddevice as sd
import mss.tools

# audio stream configuration: 16khz mono int16, 512 samples per block (32ms)
SAMPLE_RATE = 16000
BLOCKSIZE = 512
CHANNELS = 1
DTYPE = np.int16

# VAD state machine tuning (all values in frames at 32ms each)
VAD_THRESHOLD = 0.8 # speech probability cutoff (0.5 deixa música passar como fala)
TRIGGER_FRAMES = 10 # ~320ms of continous speech to open a segment
HANGOVER_FRAMES = 15
PRE_TRIGGER_FRAMES = 10
MIN_SPEECH_SAMPLES = int(SAMPLE_RATE * 0.25)
RMS_THRESHOLD = 300.0 # abaixo disso descarta como ruído/música de fundo

class AudioCapture:
    # Captures audio from the default input device, runs Silero VAD, segments, speech, captures a desktop screenshot on speech_start
    def __init__(
            self,
            output_queue: "queue.Queue[np.ndarray]",
            stop_event: threading.Event,
    ) -> None:
        # Queue that receives finished audio segments (np.ndarray int16, 16khz)
        self.output_queue = output_queue
        # Set by the orchestrator to request graceful shutdown
        self.stop_event = stop_event

        # Load Silero VAD ONNX model (inference runs via onnxruntime on CPU).
        # The silero-vad pip package bundles the ONNX model;
        self._model = load_silero_vad(onnx=True)

        # VAD State Machine
        self._is_speech = False # True while we are inside a speech segment
        self._trigger_count = 0 # consecutive pre trigger speech frames
        self._speech_buffer: list[np.ndarray] = [] # chunks of the active segment
        self._ring_buffer: list[np.ndarray] = [] # last N frames for pre-trigger padding
        self._speech_frames = 0 # frames accumulated in the current segment
        self._silence_frames = 0 # consecutive silence frames (hangover counter)

        # Latest screenshot captured at the most recent speech_start
        # Read by the orchestrator and attached to the next LLM turn
        self._latest_screenshot: Optional[bytes] = None
        self._screenshot_lock = threading.Lock() # protects _latest_screenshot
        self._mss = MSS()

        # Quando True, o callback descarta áudio (evita eco do próprio assistente)
        self._muted = False
        self._mute_lock = threading.Lock()

        self._stream: Optional[sd.InputStream] = None
        self._on_speech_start_cb: Optional[callable] = None

    def _capture_screenshot(self) -> bytes:
        # Grab the primary monitor screenshot
        monitor = self._mss.monitors[1]
        shot = self._mss.grab(monitor)
        return mss.tools.to_png(shot.rgb, shot.size) #type: ignore

    def set_muted(self, muted: bool) -> None:
        # Quando True, descarta áudio no callback (evita o eco do próprio TTS).
        # Deve ser chamado pelo playback quando começa/para de tocar.
        with self._mute_lock:
            self._muted = muted
        if not muted and self._is_speech:
            self._end_speech()

    def _start_speech(self) -> None:
        # Transition IDLE -> Speaking. Prepends the ring buffer to the segment
        self._is_speech = True
        self._speech_frames = 1
        self._silence_frames = 0
        # Ring buffer already contains the last PRE_TRIGGER_FRAMES frames
        self._speech_buffer = list(self._ring_buffer)

        # Screenshot is stored thread-safely; the orchestrator 
        # will pick it up when it processes the next transcript
        with self._screenshot_lock:
            self._latest_screenshot = self._capture_screenshot()

        if self._on_speech_start_cb is not None:
            self._on_speech_start_cb()

    def _end_speech(self) -> None:
        # Transition Speaking -> IDLE. Emits the accumulated segment to the output queue
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
        # sounddevice callback: runs in a PortAudio-managed thread, must be non-blocking. Called every BLOCKSIZE samples (32ms)
        if self.stop_event.is_set():
            raise sd.CallbackStop

        # Eco do próprio TTS: enquanto o assistente fala, o VAD continua rodando
        # apenas para detectar barge-in. Se um segmento já foi aberto por
        # barge-in, os frames continuam acumulando normalmente.
        with self._mute_lock:
            if self._muted and not self._is_speech:
                frame = indata[:, 0].copy()
                self._ring_buffer.append(frame)
                if len(self._ring_buffer) > PRE_TRIGGER_FRAMES:
                    self._ring_buffer.pop(0)
                frame_tensor = torch.from_numpy(frame.astype(np.float32) / 32768.0)
                prob = self._model(frame_tensor, SAMPLE_RATE).item()
                rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
                # fala provável E energia alta => usuário quer interromper
                if prob >= VAD_THRESHOLD and rms >= RMS_THRESHOLD * 1.5:
                    if self._on_speech_start_cb is not None:
                        self._on_speech_start_cb()
                    # abre segmento já, p/ não perder a fala do barge-in
                    self._is_speech = True
                    self._speech_frames = 1
                    self._silence_frames = 0
                    self._speech_buffer = list(self._ring_buffer[:-1])
                return

        # Convert (frames, channels) to 1-D mono int16 for downstream use
        frame = indata[:, 0].copy()

        # Always update the ring buffer so the segment start is preserved even when we are currently idle
        self._ring_buffer.append(frame)
        if len(self._ring_buffer) > PRE_TRIGGER_FRAMES:
            self._ring_buffer.pop(0)

        # Run VAD inference: int16 PCM -> float32 [-1, 1] -> torch tensor
        # Silero's wrapper returns the speech probability in [0, 1]
        frame_tensor = torch.from_numpy(frame.astype(np.float32) / 32768.0)
        prob = self._model(frame_tensor, SAMPLE_RATE).item()

        # Filtro de energia: música/ruído tem RMS baixo; fala humana próxima é alto.
        rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))

        if not self._is_speech:
            # IDLE: só abre segmento se for fala provável E com energia suficiente
            if prob >= VAD_THRESHOLD and rms >= RMS_THRESHOLD:
                self._trigger_count += 1
                if self._trigger_count >= TRIGGER_FRAMES:
                    self._start_speech()
            else:
                self._trigger_count = 0
        else:
            # SPEAKING: fala clara mantém; silêncio incrementa o hangover
            if prob >= VAD_THRESHOLD and rms >= RMS_THRESHOLD:
                self._speech_buffer.append(frame)
                self._speech_frames += 1
                self._silence_frames = 0
            else:
                self._speech_buffer.append(frame)
                self._silence_frames += 1
                if self._silence_frames >= HANGOVER_FRAMES:
                        self._end_speech()
    def set_on_speech_start(self, cb: callable) -> None:
        # Register an optional callback fired at every speech_start
        self._on_speech_start_cb = cb

    def get_latest_screenshot(self) -> Optional[bytes]:
        # Thread-safe read of the latest screenshot taken at speech_start
        with self._screenshot_lock:
            return self._latest_screenshot

    def clear_screenshot(self) -> None:
        # Clears the screenshot after the orchestrator has consumed it
        with self._screenshot_lock:
            self._latest_screenshot = None

    def start(self) -> None:
        # Open the input stream. If the default device fails, fall back to the first available input device
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
        # Cooperative shutdown: signal stop, flush the current segment, close the stream and the screen-capture handle
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
        # True while we are inside a speech segment (between start and end)
        return self._is_speech

# Test the application
if __name__ == "__main__":
    import signal
    q: "queue.Queue[np.ndarray]" = queue.Queue()
    stop = threading.Event()
    capture = AudioCapture(q, stop)

    capture.set_on_speech_start(lambda: print(" [speech_start] sreenshot"))
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
                print(f"   segment: {duration_s:.2f}s ({len(segment)} samples)")
            except queue.Empty:
                pass
    finally:
        capture.stop()
        print("Stopped.")



