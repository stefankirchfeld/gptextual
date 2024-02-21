from datetime import datetime, timezone
import asyncio


def format_timestamp(timestamp: float) -> str:
    """Convert a Unix timestamp into a string in human-readable format.

    Args:
        timestamp: The Unix timestamp.

    Returns:
        The string timestamp in the format "%Y-%m-%d %H:%M:%S".
    """
    utc_dt = datetime.fromtimestamp(timestamp, timezone.utc)
    local_dt = utc_dt.astimezone()
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


def single_css_class(name, prop, val):
    return f"""
    .{name} {'{'}
     {prop}: {val};   
    {'}'}
  """


class AsyncCache:
    def __init__(self):
        self.cache = {}
        self.in_progress = {}

    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            if key not in self.cache:
                if key not in self.in_progress:
                    self.in_progress[key] = asyncio.create_task(func(*args, **kwargs))
                    self.cache[key] = await self.in_progress[key]
                    del self.in_progress[key]
                else:
                    await self.in_progress[key]
                    # Now the result is in the cache
            return self.cache[key]

        return wrapper
