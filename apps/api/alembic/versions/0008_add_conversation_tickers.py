"""add tickers to conversations

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("tickers", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "tickers")

