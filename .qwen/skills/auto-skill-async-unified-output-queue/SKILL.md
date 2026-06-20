---
name: async-unified-output-queue
description: Pattern for Python async pipelines — funnel multiple concurrent producers of heterogeneous types into a single output queue with sentinel-based termination
source: auto-skill
extracted_at: '2026-06-19T14:26:19.242Z'
---

# Unified Output Queue for Async Pipelines

## When to use

When building an async generator that coordinates multiple concurrent tasks producing **different output types** (e.g., text dicts + audio bytes, or progress events + result data), and you want to yield them interleaved in real-time rather than batching at the end.

## The pattern

Instead of separate queues per output type, use **one shared output queue** typed as `asyncio.Queue[Union[TypeA, TypeB, None]]`. Each producer writes its items and pushes a `None` sentinel when done. The consumer counts sentinels to know when all producers are finished.

### Producer side

Each concurrent task writes its own output type and signals completion:

```python
async def _producer_a(output_queue: asyncio.Queue, ...) -> None:
    try:
        async for item in source_a():
            await output_queue.put({"type": "text_delta", "text": item})
    except Exception as e:
        await error_queue.put(e)
    finally:
        await output_queue.put(None)  # sentinel: producer A done

async def _producer_b(output_queue: asyncio.Queue, ...) -> None:
    try:
        async for chunk in source_b():
            await output_queue.put(chunk)  # raw bytes
    except Exception as e:
        await error_queue.put(e)
    finally:
        await output_queue.put(None)  # sentinel: producer B done
```

### Consumer side (the async generator)

Count sentinels to know when all N producers have finished:

```python
async def run(self) -> AsyncGenerator[bytes | dict, None]:
    output_queue: asyncio.Queue[bytes | dict | None] = asyncio.Queue()
    error_queue: asyncio.Queue[Exception] = asyncio.Queue()

    task_a = asyncio.create_task(_producer_a(output_queue, ...))
    task_b = asyncio.create_task(_producer_b(output_queue, ...))

    sentinels_seen = 0
    NUM_PRODUCERS = 2

    try:
        while sentinels_seen < NUM_PRODUCERS:
            try:
                item = await asyncio.wait_for(
                    output_queue.get(), timeout=30.0
                )
            except asyncio.TimeoutError:
                break

            if item is None:
                sentinels_seen += 1
                continue

            yield item
    finally:
        task_a.cancel()
        task_b.cancel()
        await asyncio.gather(task_a, task_b, return_exceptions=True)

    if not error_queue.empty():
        raise await error_queue.get()
```

## Why this over separate queues

- **Interleaving**: Text deltas and audio arrive mixed naturally as they're produced — no need to drain one queue before the other
- **Single yield point**: The async generator has one `yield` in one loop, not a complex merge of multiple drains
- **Clean termination**: Sentinel counting is simpler than tracking per-queue completion with flags or `asyncio.wait`

## Gotchas

- The consumer must know the total number of producers (`NUM_PRODUCERS`) to count sentinels correctly
- Use `try/finally` in every producer to guarantee the sentinel is pushed, even on exception
- A separate `error_queue` is needed since you can't raise from inside a producer task — the consumer checks it after draining
- If a producer can legitimately produce `None` as data, use a dedicated sentinel object instead: `_SENTINEL = object()`
