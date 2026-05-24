"""create indexing tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_index_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column("doc_id", sa.String(length=36), nullable=False),
        sa.Column("parse_run_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_run_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("backend", sa.String(length=20), nullable=False, server_default="opensearch"),
        sa.Column("index_name", sa.String(length=255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("indexed_chunks", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_document_index_runs_doc_id", "document_index_runs", ["doc_id"])
    op.create_index("ix_document_index_runs_parse_run_id", "document_index_runs", ["parse_run_id"])
    op.create_index("ix_document_index_runs_chunk_run_id", "document_index_runs", ["chunk_run_id"])
    op.create_index("ix_document_index_runs_status", "document_index_runs", ["status"])
    op.create_index("ix_document_index_runs_backend", "document_index_runs", ["backend"])
    op.create_index("ix_document_index_runs_index_name", "document_index_runs", ["index_name"])


def downgrade() -> None:
    op.drop_index("ix_document_index_runs_index_name", table_name="document_index_runs")
    op.drop_index("ix_document_index_runs_backend", table_name="document_index_runs")
    op.drop_index("ix_document_index_runs_status", table_name="document_index_runs")
    op.drop_index("ix_document_index_runs_chunk_run_id", table_name="document_index_runs")
    op.drop_index("ix_document_index_runs_parse_run_id", table_name="document_index_runs")
    op.drop_index("ix_document_index_runs_doc_id", table_name="document_index_runs")
    op.drop_table("document_index_runs")

