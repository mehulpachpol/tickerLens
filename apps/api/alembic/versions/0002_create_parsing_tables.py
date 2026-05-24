"""create parsing tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_parse_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column("doc_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("parser_version", sa.String(length=50), nullable=False, server_default="pymupdf+tesseract:v1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("ocr_page_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_document_parse_runs_doc_id", "document_parse_runs", ["doc_id"])
    op.create_index("ix_document_parse_runs_status", "document_parse_runs", ["status"])

    op.create_table(
        "document_pages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("doc_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("page_num", sa.Integer(), nullable=False),
        sa.Column("extraction_method", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_document_pages_doc_id", "document_pages", ["doc_id"])
    op.create_index("ix_document_pages_run_id", "document_pages", ["run_id"])
    op.create_index("ix_document_pages_checksum", "document_pages", ["checksum"])
    op.create_unique_constraint("uq_document_pages_run_page", "document_pages", ["run_id", "page_num"])


def downgrade() -> None:
    op.drop_constraint("uq_document_pages_run_page", "document_pages", type_="unique")
    op.drop_index("ix_document_pages_checksum", table_name="document_pages")
    op.drop_index("ix_document_pages_run_id", table_name="document_pages")
    op.drop_index("ix_document_pages_doc_id", table_name="document_pages")
    op.drop_table("document_pages")

    op.drop_index("ix_document_parse_runs_status", table_name="document_parse_runs")
    op.drop_index("ix_document_parse_runs_doc_id", table_name="document_parse_runs")
    op.drop_table("document_parse_runs")

