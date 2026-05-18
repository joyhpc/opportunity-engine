"""Async helpers for explicit blocking-work offload."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


async def run_blocking(func: Callable[..., T], /, *args, **kwargs) -> T:
    """Run known synchronous I/O or CPU work without blocking the event loop."""

    return await asyncio.to_thread(func, *args, **kwargs)
