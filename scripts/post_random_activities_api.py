#!/usr/bin/env python3
"""Post random activity records to the activities API."""

from __future__ import annotations

import argparse
import csv
import random
import re
import time
from collections.abc import Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, as_completed, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from faker import Faker

DEFAULT_BASE_URL = "https://dev.active10.betterhealthapps.com"
DEFAULT_DAYS_BACK = 365
DEFAULT_CONCURRENCY = 4
DEFAULT_FAILURE_PRINT_LIMIT = 20
MIGRATION_BATCH_ACTIVITIES = 30
PENDING_REQUEST_MULTIPLIER = 4
REWARD_PROBABILITY = 0.25
TOKEN_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
AGE_RANGES = ("18-22", "23-39", "40-59", "60-74", "75+")
REWARD_SLUGS = ("high_five", "streak", "goal_hit", "brisk_walk", "daily_target")


@dataclass(frozen=True)
class Config:
    base_url: str
    endpoint: str
    migration_endpoint: str
    count: int
    tokens: list[str]
    days_back: int
    concurrency: int
    timeout: float
    dry_run: bool
    use_migrations: bool
    seed: int | None
    locale: str


@dataclass(frozen=True)
class PostResult:
    index: int
    status_code: int | None
    ok: bool
    message: str
    activity_count: int


@dataclass(frozen=True)
class ApiRequest:
    index: int
    token: str
    payload: dict[str, Any]
    activity_count: int


def read_tokens_from_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")

    if path.suffix.lower() == ".csv":
        rows = csv.DictReader(text.splitlines())
        if rows.fieldnames and "token" in rows.fieldnames:
            return [row["token"].strip() for row in rows if row.get("token")]

    tokens = TOKEN_PATTERN.findall(text)
    if tokens:
        return tokens

    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def activity_endpoint(base_url: str, endpoint: str) -> str:
    return f"{base_url.rstrip('/')}/{endpoint.strip('/')}"


def random_unix_timestamp(days_back: int) -> int:
    now = int(time.time())
    earliest = now - (days_back * 24 * 60 * 60)
    return random.randint(earliest, now)


def month_marker_timestamp(timestamp: int) -> int:
    activity_datetime = datetime.fromtimestamp(timestamp, timezone.utc)  # noqa: UP017
    month_marker = activity_datetime.replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    return int(month_marker.timestamp())


def month_bounds(month_marker: int, days_back: int) -> tuple[int, int]:
    marker_datetime = datetime.fromtimestamp(month_marker, timezone.utc)  # noqa: UP017
    month_start = marker_datetime.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if month_start.month == 12:  # noqa: PLR2004
        next_month_start = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1)

    earliest = int(time.time()) - (days_back * 24 * 60 * 60)
    latest = int(time.time())
    return max(int(month_start.timestamp()), earliest), min(
        int(next_month_start.timestamp()) - 1,
        latest,
    )


def build_activity_payload(fake: Faker, timestamp: int) -> dict[str, Any]:
    walking_minutes = random.randint(5, 120)
    brisk_minutes = random.randint(0, walking_minutes)
    steps = max(1, int(walking_minutes * random.randint(70, 140)))
    rewards = []

    if random.random() < REWARD_PROBABILITY:
        rewards.append(
            {
                "earned": random.randint(1, 100),
                "slug": random.choice(REWARD_SLUGS),
            }
        )

    return {
        "date": timestamp,
        "user_postcode": fake.postcode().replace(" ", "")[:10],
        "user_age_range": random.choice(AGE_RANGES),
        "rewards": rewards,
        "activity": {
            "brisk_minutes": brisk_minutes,
            "walking_minutes": walking_minutes,
            "steps": steps,
        },
    }


def build_random_activity_payload(fake: Faker, days_back: int) -> dict[str, Any]:
    return build_activity_payload(fake, random_unix_timestamp(days_back))


def iter_single_activity_requests(config: Config, fake: Faker) -> Iterator[ApiRequest]:
    for index in range(1, config.count + 1):
        yield ApiRequest(
            index=index,
            token=config.tokens[(index - 1) % len(config.tokens)],
            payload=build_random_activity_payload(fake, config.days_back),
            activity_count=1,
        )


def planned_migration_request_count(activity_count: int) -> int:
    return (activity_count + MIGRATION_BATCH_ACTIVITIES - 1) // MIGRATION_BATCH_ACTIVITIES


def iter_migration_requests(config: Config, fake: Faker) -> Iterator[ApiRequest]:
    request_count = planned_migration_request_count(config.count)

    for request_index in range(1, request_count + 1):
        month = month_marker_timestamp(random_unix_timestamp(config.days_back))
        month_start, month_end = month_bounds(month, config.days_back)
        activities = [
            build_activity_payload(fake, random.randint(month_start, month_end))
            for _ in range(MIGRATION_BATCH_ACTIVITIES)
        ]

        yield ApiRequest(
            index=request_index,
            token=config.tokens[(request_index - 1) % len(config.tokens)],
            payload={"month": month, "activities": activities},
            activity_count=len(activities),
        )


def post_activity(
    *,
    url: str,
    api_request: ApiRequest,
    timeout: float,
) -> PostResult:
    try:
        response = requests.post(
            url,
            json=api_request.payload,
            headers={"Authorization": f"Bearer {api_request.token}"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return PostResult(
            index=api_request.index,
            status_code=None,
            ok=False,
            message=str(exc),
            activity_count=api_request.activity_count,
        )

    if response.ok:
        return PostResult(
            index=api_request.index,
            status_code=response.status_code,
            ok=True,
            message="OK",
            activity_count=api_request.activity_count,
        )

    return PostResult(
        index=api_request.index,
        status_code=response.status_code,
        ok=False,
        message=response.text[:500],
        activity_count=api_request.activity_count,
    )


def collect_result(result: PostResult, failures: list[PostResult]) -> int:
    if result.ok:
        return result.activity_count

    failures.append(result)
    return 0


def post_requests(
    *,
    config: Config,
    url: str,
    requests_to_send: Iterator[ApiRequest],
) -> tuple[int, list[PostResult], int]:
    failures: list[PostResult] = []
    successful_activities = 0
    submitted_requests = 0
    max_pending = max(1, config.concurrency * PENDING_REQUEST_MULTIPLIER)

    with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
        pending: set[Future[PostResult]] = set()

        for api_request in requests_to_send:
            pending.add(
                executor.submit(
                    post_activity,
                    url=url,
                    api_request=api_request,
                    timeout=config.timeout,
                )
            )
            submitted_requests += 1

            if len(pending) >= max_pending:
                completed, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in completed:
                    successful_activities += collect_result(future.result(), failures)

        for future in as_completed(pending):
            successful_activities += collect_result(future.result(), failures)

    return successful_activities, failures, submitted_requests


def run(config: Config) -> int:
    if config.count < 1:
        raise ValueError("count must be greater than zero")
    if not config.tokens:
        raise ValueError("at least one bearer token is required")
    if config.days_back < 1:
        raise ValueError("days_back must be greater than zero")
    if config.concurrency < 1:
        raise ValueError("concurrency must be greater than zero")

    if config.seed is not None:
        Faker.seed(config.seed)
        random.seed(config.seed)

    fake = Faker(config.locale)
    url = activity_endpoint(
        config.base_url,
        config.migration_endpoint if config.use_migrations else config.endpoint,
    )
    requests_to_send = (
        iter_migration_requests(config, fake)
        if config.use_migrations
        else iter_single_activity_requests(config, fake)
    )
    planned_request_count = (
        planned_migration_request_count(config.count) if config.use_migrations else config.count
    )
    planned_activity_count = (
        planned_request_count * MIGRATION_BATCH_ACTIVITIES
        if config.use_migrations
        else config.count
    )

    if config.dry_run:
        print(next(requests_to_send).payload)
        print(
            f"Would send {planned_request_count} request(s) for {planned_activity_count} activities"
        )
        return 0

    successful_activities, failures, submitted_requests = post_requests(
        config=config,
        url=url,
        requests_to_send=requests_to_send,
    )

    print(
        f"Posted {successful_activities}/{planned_activity_count} activities to {url} "
        f"using {submitted_requests} request(s)"
    )

    if failures:
        print("Failures:")
        for failure in sorted(failures, key=lambda item: item.index)[:DEFAULT_FAILURE_PRINT_LIMIT]:
            status = failure.status_code if failure.status_code is not None else "request-error"
            print(f"  #{failure.index}: {status} {failure.message}")
        if len(failures) > DEFAULT_FAILURE_PRINT_LIMIT:
            print(f"  ... {len(failures) - DEFAULT_FAILURE_PRINT_LIMIT} more")
        return 1

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Post random activity records to the API.")
    parser.add_argument("count", type=int, help="Number of activity records to post.")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL. Defaults to {DEFAULT_BASE_URL}.",
    )
    parser.add_argument(
        "--endpoint",
        default="/v1/activities",
        help="Activities endpoint path. Defaults to /v1/activities.",
    )
    parser.add_argument(
        "--migration-endpoint",
        default="/v1/migrations/activities",
        help="Activities migration endpoint path. Defaults to /v1/migrations/activities.",
    )
    parser.add_argument(
        "--use-migrations",
        action="store_true",
        help="Use the activities migration endpoint to send 30 activities per request.",
    )
    parser.add_argument("--token", action="append", default=[], help="Bearer token to use.")
    parser.add_argument(
        "--tokens-file",
        type=Path,
        help="File containing tokens. Supports one token per line, CSV with token column, or SQL.",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=DEFAULT_DAYS_BACK,
        help=f"Randomly choose dates from the last N days. Defaults to {DEFAULT_DAYS_BACK}.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Number of parallel requests. Defaults to {DEFAULT_CONCURRENCY}.",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout in seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Print one payload without posting.")
    parser.add_argument("--seed", type=int, default=None, help="Optional seed for repeatable data.")
    parser.add_argument("--locale", default="en_GB", help="Faker locale. Defaults to en_GB.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tokens = [token.strip() for token in args.token if token.strip()]

    if args.tokens_file:
        tokens.extend(read_tokens_from_file(args.tokens_file))

    config = Config(
        base_url=args.base_url,
        endpoint=args.endpoint,
        migration_endpoint=args.migration_endpoint,
        count=args.count,
        tokens=tokens,
        days_back=args.days_back,
        concurrency=args.concurrency,
        timeout=args.timeout,
        dry_run=args.dry_run,
        use_migrations=args.use_migrations,
        seed=args.seed,
        locale=args.locale,
    )
    raise SystemExit(run(config))


if __name__ == "__main__":
    main()
