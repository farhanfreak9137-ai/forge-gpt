from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp (drop-in for the deprecated datetime.utcnow())."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
