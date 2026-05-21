#!/usr/bin/env python3
"""Generate SQL inserts for fake users."""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from faker import Faker

DEFAULT_BATCH_SIZE = 1000
NHS_CHECKSUM_BASE = 11
NHS_INVALID_CHECKSUM = 10


@dataclass(frozen=True)
class UserRow:
    id: str
    unique_id: str
    nhs_number: str
    first_name: str
    email: str
    date_of_birth: date
    gender: str
    postcode: str
    identity_level: str
    status_updated_at: datetime


@dataclass(frozen=True)
class GeneratorConfig:
    count: int
    output_path: Path
    batch_size: int
    locale: str
    seed: int | None


def sql_string(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def sql_date(value: date | None) -> str:
    if value is None:
        return "NULL"
    return sql_string(value.isoformat())


def sql_timestamp(value: datetime) -> str:
    return sql_string(value.replace(tzinfo=None).isoformat(sep=" ", timespec="seconds"))


def generate_nhs_number() -> str:
    """Generate a syntactically valid NHS number using the modulus 11 checksum."""
    while True:
        digits = [random.randint(1, 9), *[random.randint(0, 9) for _ in range(8)]]
        weighted_sum = sum(
            digit * weight for digit, weight in zip(digits, range(10, 1, -1), strict=True)
        )
        checksum = NHS_CHECKSUM_BASE - (weighted_sum % NHS_CHECKSUM_BASE)

        if checksum == NHS_CHECKSUM_BASE:
            checksum = 0
        if checksum != NHS_INVALID_CHECKSUM:
            return "".join(str(digit) for digit in [*digits, checksum])


def build_user_values(user: UserRow) -> str:
    return (
        f"({sql_string(user.id)}, {sql_string(user.unique_id)}, {sql_string(user.nhs_number)}, "
        f"{sql_string(user.first_name[:50])}, {sql_string(user.email[:254])}, "
        f"{sql_date(user.date_of_birth)}, {sql_string(user.gender[:6])}, "
        f"{sql_string(user.postcode[:10])}, {sql_string(user.identity_level)}, "
        f"{sql_string('Login')}, {sql_timestamp(user.status_updated_at)})"
    )


def write_batched_insert(sql_file, table: str, columns: tuple[str, ...], values: list[str]) -> None:
    if not values:
        return

    sql_file.write(f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n")
    sql_file.write(",\n".join(values))
    sql_file.write(";\n")


def write_user_batch(
    sql_file,
    user_values: list[str],
) -> None:
    write_batched_insert(
        sql_file,
        "users",
        (
            "id",
            "unique_id",
            "nhs_number",
            "first_name",
            "email",
            "date_of_birth",
            "gender",
            "postcode",
            "identity_level",
            "status",
            "status_updated_at",
        ),
        user_values,
    )
    sql_file.write("\n")


def write_sql_file(config: GeneratorConfig) -> None:
    if config.count < 1:
        raise ValueError("count must be greater than zero")
    if config.batch_size < 1:
        raise ValueError("batch_size must be greater than zero")

    fake = Faker(config.locale)
    if config.seed is not None:
        Faker.seed(config.seed)
        random.seed(config.seed)

    now = datetime.now(timezone.utc)  # noqa: UP017 Not supported in Python 3.10

    with config.output_path.open("w", encoding="utf-8") as sql_file:
        sql_file.write("-- Generated fake users.\n")
        sql_file.write("-- Insert manually with psql or your preferred PostgreSQL client.\n")
        sql_file.write(f"-- Batch size: {config.batch_size}\n")
        sql_file.write("BEGIN;\n\n")

        user_values: list[str] = []

        for _ in range(config.count):
            user_id = str(uuid4())
            gender = random.choice(["Male", "Female", "Other"])

            user = UserRow(
                id=user_id,
                unique_id=str(uuid4()),
                nhs_number=generate_nhs_number(),
                first_name=fake.first_name(),
                email=fake.unique.email(),
                date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=95),
                gender=gender,
                postcode=fake.postcode().replace(" ", ""),
                identity_level="P5",
                status_updated_at=now,
            )

            user_values.append(build_user_values(user))

            if len(user_values) >= config.batch_size:
                write_user_batch(sql_file, user_values)
                user_values.clear()

        write_user_batch(sql_file, user_values)

        sql_file.write("COMMIT;\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a PostgreSQL SQL file containing fake users."
    )
    parser.add_argument("count", type=int, help="Number of users to generate.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("generated_users.sql"),
        help="SQL output path. Defaults to generated_users.sql.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Rows per multi-row INSERT. Defaults to {DEFAULT_BATCH_SIZE}.",
    )
    parser.add_argument(
        "--locale",
        default="en_GB",
        help="Faker locale. Defaults to en_GB.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional seed for repeatable output.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = GeneratorConfig(
        count=args.count,
        output_path=args.output,
        batch_size=args.batch_size,
        locale=args.locale,
        seed=args.seed,
    )
    write_sql_file(config)
    print(f"Wrote {args.count} users to {args.output}")


if __name__ == "__main__":
    main()
