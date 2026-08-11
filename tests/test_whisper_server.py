from servers.whisper import WhisperServer
from pathlib import Path

s = WhisperServer(Path('bin/whisper-server'), Path("models/whisper/ggml-small.bin"))
s.start()
input("servidor ativo! Aperte Enter para parar...\n")
s.stop()
print("servidor parado")