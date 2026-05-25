"""create ticker universes and auto ingestion tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticker_universes",
        sa.Column("universe_id", sa.String(length=50), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "ticker_universe_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "universe_id",
            sa.String(length=50),
            sa.ForeignKey("ticker_universes.universe_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ticker_universe_members_universe_id", "ticker_universe_members", ["universe_id"])
    op.create_index("ix_ticker_universe_members_ticker", "ticker_universe_members", ["ticker"])
    op.create_unique_constraint(
        "uq_ticker_universe_members_universe_ticker",
        "ticker_universe_members",
        ["universe_id", "ticker"],
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "universe_id",
            sa.String(length=50),
            sa.ForeignKey("ticker_universes.universe_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("job_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("discovered_items", sa.Integer(), nullable=True),
        sa.Column("downloaded_items", sa.Integer(), nullable=True),
        sa.Column("ingested_items", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ingestion_runs_universe_id", "ingestion_runs", ["universe_id"])
    op.create_index("ix_ingestion_runs_ticker", "ingestion_runs", ["ticker"])
    op.create_index("ix_ingestion_runs_job_type", "ingestion_runs", ["job_type"])
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])
    op.create_index("ix_ingestion_runs_scheduled_for", "ingestion_runs", ["scheduled_for"])

    op.create_table(
        "ingestion_discovered_items",
        sa.Column("item_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "universe_id",
            sa.String(length=50),
            sa.ForeignKey("ticker_universes.universe_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default=sa.text("'nse'")),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("document_type", sa.String(length=50), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'discovered'")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("doc_id", sa.String(length=36), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ingestion_discovered_items_universe_id", "ingestion_discovered_items", ["universe_id"])
    op.create_index("ix_ingestion_discovered_items_ticker", "ingestion_discovered_items", ["ticker"])
    op.create_index("ix_ingestion_discovered_items_source", "ingestion_discovered_items", ["source"])
    op.create_index("ix_ingestion_discovered_items_fingerprint", "ingestion_discovered_items", ["fingerprint"])
    op.create_index("ix_ingestion_discovered_items_document_type", "ingestion_discovered_items", ["document_type"])
    op.create_index("ix_ingestion_discovered_items_published_at", "ingestion_discovered_items", ["published_at"])
    op.create_index("ix_ingestion_discovered_items_status", "ingestion_discovered_items", ["status"])
    op.create_index("ix_ingestion_discovered_items_doc_id", "ingestion_discovered_items", ["doc_id"])
    op.create_index("ix_ingestion_discovered_items_checksum", "ingestion_discovered_items", ["checksum"])
    op.create_unique_constraint(
        "uq_ingestion_discovered_items_universe_ticker_fingerprint",
        "ingestion_discovered_items",
        ["universe_id", "ticker", "fingerprint"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_ingestion_discovered_items_universe_ticker_fingerprint",
        "ingestion_discovered_items",
        type_="unique",
    )
    op.drop_index("ix_ingestion_discovered_items_checksum", table_name="ingestion_discovered_items")
    op.drop_index("ix_ingestion_discovered_items_doc_id", table_name="ingestion_discovered_items")
    op.drop_index("ix_ingestion_discovered_items_status", table_name="ingestion_discovered_items")
    op.drop_index("ix_ingestion_discovered_items_published_at", table_name="ingestion_discovered_items")
    op.drop_index("ix_ingestion_discovered_items_document_type", table_name="ingestion_discovered_items")
    op.drop_index("ix_ingestion_discovered_items_fingerprint", table_name="ingestion_discovered_items")
    op.drop_index("ix_ingestion_discovered_items_source", table_name="ingestion_discovered_items")
    op.drop_index("ix_ingestion_discovered_items_ticker", table_name="ingestion_discovered_items")
    op.drop_index("ix_ingestion_discovered_items_universe_id", table_name="ingestion_discovered_items")
    op.drop_table("ingestion_discovered_items")

    op.drop_index("ix_ingestion_runs_scheduled_for", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_status", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_job_type", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_ticker", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_universe_id", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")

    op.drop_constraint(
        "uq_ticker_universe_members_universe_ticker",
        "ticker_universe_members",
        type_="unique",
    )
    op.drop_index("ix_ticker_universe_members_ticker", table_name="ticker_universe_members")
    op.drop_index("ix_ticker_universe_members_universe_id", table_name="ticker_universe_members")
    op.drop_table("ticker_universe_members")

    op.drop_table("ticker_universes")
