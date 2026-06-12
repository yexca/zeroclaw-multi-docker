import json
import os
import random
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


STATE_DIR = Path(os.environ.get("PROACTIVE_STATE_DIR", "/state"))
DB_PATH = STATE_DIR / "proactive.sqlite3"


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"{name}={raw!r} is invalid; using {default}", flush=True)
        return default


def parse_mapping(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            result[key] = value
    return result


def parse_quiet_hours(raw: str) -> tuple[int, int] | None:
    raw = raw.strip()
    if not raw:
        return None
    if "-" not in raw:
        raise ValueError("PROACTIVE_QUIET_HOURS must look like 23-8")
    start_raw, end_raw = raw.split("-", 1)
    start = int(start_raw)
    end = int(end_raw)
    if not 0 <= start <= 23 or not 0 <= end <= 23:
        raise ValueError("quiet hour values must be between 0 and 23")
    return start, end


def is_quiet(now: datetime, quiet: tuple[int, int] | None) -> bool:
    if quiet is None:
        return False
    start, end = quiet
    hour = now.hour
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def db() -> sqlite3.Connection:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS proactive_runs (
            bot TEXT PRIMARY KEY,
            last_attempt_at INTEGER,
            next_wake_at INTEGER
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(proactive_runs)")}
    if "next_wake_at" not in columns:
        conn.execute("ALTER TABLE proactive_runs ADD COLUMN next_wake_at INTEGER")
    conn.commit()
    return conn


def format_local(ts: int, tz: timezone | ZoneInfo) -> str:
    return datetime.fromtimestamp(ts, tz).isoformat(timespec="seconds")


def random_interval_seconds(min_minutes: int, max_minutes: int) -> int:
    return random.randint(min_minutes * 60, max_minutes * 60)


def get_next_wake(conn: sqlite3.Connection, bot: str) -> int | None:
    row = conn.execute(
        "SELECT next_wake_at FROM proactive_runs WHERE bot = ?",
        (bot,),
    ).fetchone()
    if row is None:
        return None
    if row[0] is None:
        return None
    return int(row[0])


def schedule_next(
    conn: sqlite3.Connection,
    bot: str,
    base_ts: int,
    min_minutes: int,
    max_minutes: int,
    tz: timezone | ZoneInfo,
    reason: str,
) -> int:
    next_wake_at = base_ts + random_interval_seconds(min_minutes, max_minutes)
    conn.execute(
        """
        INSERT INTO proactive_runs (bot, last_attempt_at, next_wake_at)
        VALUES (?, 0, ?)
        ON CONFLICT(bot) DO UPDATE SET next_wake_at = excluded.next_wake_at
        """,
        (bot, next_wake_at),
    )
    conn.commit()
    print(
        f"{bot}: next proactive wake {format_local(next_wake_at, tz)} ({reason})",
        flush=True,
    )
    return next_wake_at


def mark_attempt(conn: sqlite3.Connection, bot: str, attempted_at: int) -> None:
    conn.execute(
        """
        INSERT INTO proactive_runs (bot, last_attempt_at)
        VALUES (?, ?)
        ON CONFLICT(bot) DO UPDATE SET last_attempt_at = excluded.last_attempt_at
        """,
        (bot, attempted_at),
    )
    conn.commit()


def seconds_until_quiet_end(now: datetime, quiet: tuple[int, int] | None) -> int:
    if quiet is None or not is_quiet(now, quiet):
        return 0
    _, end = quiet
    quiet_end = now.replace(hour=end, minute=0, second=0, microsecond=0)
    if quiet_end <= now:
        quiet_end += timedelta(days=1)
    return max(0, int((quiet_end - now).total_seconds()))


def post_prompt(
    bot: str,
    url: str,
    channel: str,
    target: str,
    prompt_template: str,
) -> None:
    prompt = (
        prompt_template
        + f'\n\nConfigured Matrix channel for send_message_to_peer: "{channel}".'
        + f'\nConfigured Matrix peer target for send_message_to_peer: "{target}".'
        + "\nIf you send a message, you must call send_message_to_peer with channel, target, and message set to these configured values."
        + "\nKeep any outbound message short. If you decide not to contact the user, respond exactly with \"skip\"."
    )
    payload = json.dumps({"message": prompt}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Session-Id": f"proactive-{bot}",
            "X-Idempotency-Key": f"proactive-{bot}-{uuid.uuid4()}",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read(1024).decode("utf-8", errors="replace")
        print(f"{bot}: gateway returned {response.status}: {body}", flush=True)


def main() -> None:
    enabled = env_bool("PROACTIVE_ENABLED", False)
    poll_seconds = max(30, env_int("PROACTIVE_POLL_SECONDS", 300))
    legacy_cooldown_minutes = max(1, env_int("PROACTIVE_COOLDOWN_MINUTES", 120))
    random_min_minutes = max(
        1,
        env_int("PROACTIVE_RANDOM_MIN_MINUTES", legacy_cooldown_minutes),
    )
    random_max_minutes = max(
        random_min_minutes,
        env_int("PROACTIVE_RANDOM_MAX_MINUTES", random_min_minutes * 2),
    )
    timezone_name = os.environ.get("PROACTIVE_TIMEZONE", "Asia/Tokyo")
    quiet = parse_quiet_hours(os.environ.get("PROACTIVE_QUIET_HOURS", "23-8"))
    agents = parse_mapping(
        os.environ.get("PROACTIVE_AGENTS")
        or os.environ.get("PROACTIVE_BOTS", "")
    )
    channels = parse_mapping(os.environ.get("PROACTIVE_CHANNELS", ""))
    targets = parse_mapping(os.environ.get("PROACTIVE_TARGETS", ""))
    prompt = os.environ.get("PROACTIVE_PROMPT", "").strip()

    if not prompt:
        prompt = (
            "You are being invoked by the proactive sidecar, not by the user. "
            "Review HEARTBEAT.md, memory, and current context. If there is a concrete, "
            "timely reason to contact the user, send one short Matrix message with "
            "send_message_to_peer using the configured channel and peer target. "
            "If there is no useful reason, respond exactly with \"skip\"."
        )

    if not enabled:
        print("proactive sidecar disabled; set PROACTIVE_ENABLED=true to run", flush=True)
        while True:
            time.sleep(3600)

    if not agents:
        raise SystemExit("PROACTIVE_AGENTS is empty")

    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name == "Asia/Tokyo":
            tz = timezone(timedelta(hours=9), name="Asia/Tokyo")
        else:
            print(f"timezone {timezone_name!r} not found; falling back to UTC", flush=True)
            tz = timezone.utc
    conn = db()
    print(
        (
            "proactive sidecar started: "
            f"agents={list(agents)}, check={poll_seconds}s, "
            f"random={random_min_minutes}-{random_max_minutes}m"
        ),
        flush=True,
    )

    now_ts = int(time.time())
    for agent in agents:
        if get_next_wake(conn, agent) is None:
            schedule_next(
                conn,
                agent,
                now_ts,
                random_min_minutes,
                random_max_minutes,
                tz,
                "initial",
            )

    while True:
        now = datetime.now(tz)
        now_ts = int(time.time())
        if is_quiet(now, quiet):
            print(f"quiet hours active at {now.isoformat()}; skipping", flush=True)
            quiet_delay = seconds_until_quiet_end(now, quiet)
            for agent in agents:
                next_wake_at = get_next_wake(conn, agent)
                if next_wake_at is not None and next_wake_at <= now_ts:
                    schedule_next(
                        conn,
                        agent,
                        now_ts + quiet_delay,
                        random_min_minutes,
                        random_max_minutes,
                        tz,
                        "quiet-hours deferral",
                    )
            time.sleep(min(poll_seconds, max(30, quiet_delay or poll_seconds)))
            continue

        for agent, url in agents.items():
            next_wake_at = get_next_wake(conn, agent)
            if next_wake_at is None:
                schedule_next(
                    conn,
                    agent,
                    now_ts,
                    random_min_minutes,
                    random_max_minutes,
                    tz,
                    "missing schedule",
                )
                continue
            if next_wake_at > now_ts:
                continue

            channel = channels.get(agent)
            if not channel:
                print(f"{agent}: no configured channel; skipping", flush=True)
                schedule_next(
                    conn,
                    agent,
                    now_ts,
                    random_min_minutes,
                    random_max_minutes,
                    tz,
                    "missing channel",
                )
                continue
            target = targets.get(agent)
            if not target:
                print(f"{agent}: no configured target; skipping", flush=True)
                schedule_next(
                    conn,
                    agent,
                    now_ts,
                    random_min_minutes,
                    random_max_minutes,
                    tz,
                    "missing target",
                )
                continue

            mark_attempt(conn, agent, now_ts)
            try:
                post_prompt(agent, url, channel, target, prompt)
            except urllib.error.URLError as exc:
                print(f"{agent}: gateway request failed: {exc}", flush=True)
            except TimeoutError as exc:
                print(f"{agent}: gateway request timed out: {exc}", flush=True)
            finally:
                schedule_next(
                    conn,
                    agent,
                    int(time.time()),
                    random_min_minutes,
                    random_max_minutes,
                    tz,
                    "after wake",
                )

        next_wakes = [wake for agent in agents if (wake := get_next_wake(conn, agent))]
        if next_wakes:
            sleep_seconds = max(30, min(poll_seconds, min(next_wakes) - int(time.time())))
        else:
            sleep_seconds = poll_seconds
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
