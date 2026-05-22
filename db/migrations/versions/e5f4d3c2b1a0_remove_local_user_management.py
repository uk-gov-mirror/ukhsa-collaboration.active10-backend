"""remove local user management

Revision ID: e5f4d3c2b1a0
Revises: b33e91c25011
Create Date: 2026-05-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f4d3c2b1a0"
down_revision: Union[str, None] = "b33e91c25011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


USER_OWNED_TABLES = (
    ("activities", "activities_user_id_fkey", "ix_activities_user_id", False),
    ("email_preferences", "email_preferences_user_id_fkey", "ix_email_preferences_user_id", False),
    (
        "user_motivations",
        "user_motivations_user_id_fkey",
        "ix_user_motivations_user_id",
        False,
    ),
    (
        "user_activity_level",
        "user_activity_level_user_id_fkey",
        "ix_user_activity_level_user_id",
        False,
    ),
    (
        "user_daily_target",
        "user_daily_target_user_id_fkey",
        "ix_user_daily_target_user_id",
        False,
    ),
    (
        "user_walking_plan",
        "user_walking_plan_user_id_fkey",
        "ix_user_walking_plan_user_id",
        True,
    ),
    (
        "logout_user_email_logs",
        None,
        "ix_logout_user_email_logs_user_id",
        False,
    ),
    (
        "monthly_report_email_logs",
        None,
        "ix_monthly_report_email_logs_user_id",
        False,
    ),
)


def _table_exists(table_name: str) -> bool:
    return (
        op.get_bind()
        .execute(sa.text("SELECT to_regclass(:table_name)"), {"table_name": f"public.{table_name}"})
        .scalar()
        is not None
    )


def _convert_user_id_to_keycloak_subject(
    table_name: str,
    constraint_name: str | None,
    index_name: str,
    unique_index: bool,
) -> None:
    if not _table_exists(table_name):
        return

    if constraint_name:
        op.execute(
            sa.text(
                f'ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS "{constraint_name}"'
            )
        )
    op.execute(sa.text(f'DROP INDEX IF EXISTS "{index_name}"'))
    op.execute(sa.text(f'DELETE FROM "{table_name}" WHERE user_id IS NULL'))
    op.add_column(table_name, sa.Column("user_sub", sa.String(length=255), nullable=True))
    op.execute(
        sa.text(
            f"""
            UPDATE "{table_name}" AS target
            SET user_sub = users.unique_id
            FROM users
            WHERE target.user_id = users.id
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE "{table_name}"
            SET user_sub = user_id::text
            WHERE user_sub IS NULL
            AND user_id IS NOT NULL
            """
        )
    )
    op.drop_column(table_name, "user_id")
    op.alter_column(table_name, "user_sub", new_column_name="user_id")
    op.alter_column(table_name, "user_id", nullable=False)
    op.create_index(index_name, table_name, ["user_id"], unique=unique_index)


def upgrade() -> None:
    op.execute(sa.text("DROP FUNCTION IF EXISTS get_users_with_status_logout();"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS delete_user_by_id(UUID);"))

    for table_name, constraint_name, index_name, unique_index in USER_OWNED_TABLES:
        _convert_user_id_to_keycloak_subject(
            table_name=table_name,
            constraint_name=constraint_name,
            index_name=index_name,
            unique_index=unique_index,
        )

    op.drop_table("user_tokens")
    op.drop_table("delete_audit")
    op.execute(sa.text('DROP INDEX IF EXISTS "ix_users_current_token"'))
    op.execute(sa.text('DROP INDEX IF EXISTS "ix_users_unique_id"'))
    op.execute(sa.text('DROP INDEX IF EXISTS "ix_users_id"'))
    op.drop_table("users")


def downgrade() -> None:
    raise NotImplementedError(
        "Cannot downgrade after removing local user management; Keycloak subjects are not "
        "reversible to local user profile rows."
    )
