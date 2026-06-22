from datetime import datetime, timezone


def format_date(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%d.%m.%Y")


def days_left(expires_at: datetime) -> int:
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    delta = expires_at - now
    return max(0, delta.days)


def subscription_status(expires_at: datetime) -> str:
    remaining = days_left(expires_at)
    if remaining > 0:
        return "🟢 Активна"
    return "🔴 Истекла"
