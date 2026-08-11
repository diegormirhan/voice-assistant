from servers.llama import LlamaServer
from pathlib import Path

s = LlamaServer(Path('bin/llama-server'), Path("models/llm/Qwen3.5-9B-Q4_K_M.gguf"), Path("models/llm/mmproj-F16.gguf"))
s.start()
input("servidor ativo! Aperte Enter para parar...\n")
s.stop()
print("servidor parado")