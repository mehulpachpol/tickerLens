"""create chunking tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_chunk_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column("doc_id", sa.String(length=36), nullable=False),
        sa.Column("parse_run_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("chunker_version", sa.String(length=50), nullable=False, server_default="linepack:v1"),
        sa.Column("max_chunk_chars", sa.Integer(), nullable=False, server_default="5000"),
        sa.Column("overlap_chars", sa.Integer(), nullable=False, server_default="250"),
        sa.Column("max_block_chars", sa.Integer(), nullable=False, server_default="1200"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_document_chunk_runs_doc_id", "document_chunk_runs", ["doc_id"])
    op.create_index("ix_document_chunk_runs_parse_run_id", "document_chunk_runs", ["parse_run_id"])
    op.create_index("ix_document_chunk_runs_status", "document_chunk_runs", ["status"])

    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.String(length=36), primary_key=True),
        sa.Column("doc_id", sa.String(length=36), nullable=False),
        sa.Column("parse_run_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_run_id", sa.String(length=36), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_document_chunks_doc_id", "document_chunks", ["doc_id"])
    op.create_index("ix_document_chunks_parse_run_id", "document_chunks", ["parse_run_id"])
    op.create_index("ix_document_chunks_chunk_run_id", "document_chunks", ["chunk_run_id"])
    op.create_index("ix_document_chunks_ticker", "document_chunks", ["ticker"])
    op.create_index("ix_document_chunks_section", "document_chunks", ["section"])
    op.create_index("ix_document_chunks_page_start", "document_chunks", ["page_start"])
    op.create_index("ix_document_chunks_page_end", "document_chunks", ["page_end"])
    op.create_index("ix_document_chunks_checksum", "document_chunks", ["checksum"])

    op.create_table(
        "document_chunk_spans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("page_num", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_document_chunk_spans_chunk_id", "document_chunk_spans", ["chunk_id"])
    op.create_index("ix_document_chunk_spans_page_num", "document_chunk_spans", ["page_num"])


def downgrade() -> None:
    op.drop_index("ix_document_chunk_spans_page_num", table_name="document_chunk_spans")
    op.drop_index("ix_document_chunk_spans_chunk_id", table_name="document_chunk_spans")
    op.drop_table("document_chunk_spans")

    op.drop_index("ix_document_chunks_checksum", table_name="document_chunks")
    op.drop_index("ix_document_chunks_page_end", table_name="document_chunks")
    op.drop_index("ix_document_chunks_page_start", table_name="document_chunks")
    op.drop_index("ix_document_chunks_section", table_name="document_chunks")
    op.drop_index("ix_document_chunks_ticker", table_name="document_chunks")
    op.drop_index("ix_document_chunks_chunk_run_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_parse_run_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_doc_id", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index("ix_document_chunk_runs_status", table_name="document_chunk_runs")
    op.drop_index("ix_document_chunk_runs_parse_run_id", table_name="document_chunk_runs")
    op.drop_index("ix_document_chunk_runs_doc_id", table_name="document_chunk_runs")
    op.drop_table("document_chunk_runs")

