"""Polling worker that runs optimization when inputs change."""

import asyncio


async def run_worker() -> None:
    """Poll for input changes and run optimization when needed."""

    raise NotImplementedError("Worker polling logic is not yet implemented.")


def run_worker_forever() -> None:
    """Run the polling worker with an in-memory store."""
    asyncio.run(run_worker())
