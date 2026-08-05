import asyncio
import queue
import sys
import threading
import time

sys.path.insert(0, ".")


async def main():
    tq = queue.Queue()
    print("[1] testando asyncio.to_thread com queue...")

    async def get_or_empty():
        try:
            item = await asyncio.to_thread(tq.get, True, 0.1)
            print(f"  got: {item}")
        except queue.Empty:
            print("  empty")

    for i in range(3):
        await get_or_empty()

    tq.put("hello")
    print("[2] item colocado")
    await get_or_empty()
    print("[3] fim")


asyncio.run(main())
