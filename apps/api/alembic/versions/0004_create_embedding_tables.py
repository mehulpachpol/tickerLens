"""create embedding tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_embedding_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column("doc_id", sa.String(length=36), nullable=False),
        sa.Column("parse_run_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_run_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=True),
        sa.Column("vector_size", sa.Integer(), nullable=False),
        sa.Column("qdrant_collection", sa.String(length=200), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("embedded_chunks", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_document_embedding_runs_doc_id", "document_embedding_runs", ["doc_id"])
    op.create_index("ix_document_embedding_runs_parse_run_id", "document_embedding_runs", ["parse_run_id"])
    op.create_index("ix_document_embedding_runs_chunk_run_id", "document_embedding_runs", ["chunk_run_id"])
    op.create_index("ix_document_embedding_runs_status", "document_embedding_runs", ["status"])
    op.create_index("ix_document_embedding_runs_qdrant_collection", "document_embedding_runs", ["qdrant_collection"])


def downgrade() -> None:
    op.drop_index("ix_document_embedding_runs_qdrant_collection", table_name="document_embedding_runs")
    op.drop_index("ix_document_embedding_runs_status", table_name="document_embedding_runs")
    op.drop_index("ix_document_embedding_runs_chunk_run_id", table_name="document_embedding_runs")
    op.drop_index("ix_document_embedding_runs_parse_run_id", table_name="document_embedding_runs")
    op.drop_index("ix_document_embedding_runs_doc_id", table_name="document_embedding_runs")
    op.drop_table("document_embedding_runs")

