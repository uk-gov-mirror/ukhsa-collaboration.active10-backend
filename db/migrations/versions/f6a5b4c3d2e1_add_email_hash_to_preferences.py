"""add email hash to preferences

Revision ID: f6a5b4c3d2e1
Revises: e5f4d3c2b1a0
Create Date: 2026-05-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a5b4c3d2e1"
down_revision: Union[str, None] = "e5f4d3c2b1a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_preferences",
        sa.Column("email_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_email_preferences_email_hash"),
        "email_preferences",
        ["email_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_email_preferences_email_hash"), table_name="email_preferences")
    op.drop_column("email_preferences", "email_hash")
