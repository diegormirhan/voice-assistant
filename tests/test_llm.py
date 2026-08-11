import asyncio, httpx

async def debug():
    client = httpx.AsyncClient(timeout=None)
    async with client.stream("POST", "http://127.0.0.1:9992/v1/chat/completions",
                             json={"model": "qwen", "messages": [{"role":"user","content":"oi"}], "stream": True}) as resp:
        async for line in resp.aiter_lines():
            print(repr(line[:120]))   # mostra as 3-4 primeiras linhas reais
    await client.aclose()

asyncio.run(debug())