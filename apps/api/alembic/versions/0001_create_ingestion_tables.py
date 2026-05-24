"""create ingestion tables

Revision ID: 0001
Revises:
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("ticker", sa.String(length=20), primary_key=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "documents",
        sa.Column("doc_id", sa.String(length=36), primary_key=True),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("fiscal_year", sa.String(length=10), nullable=True),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_documents_ticker", "documents", ["ticker"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
    op.create_index("ix_documents_fiscal_year", "documents", ["fiscal_year"])
    op.create_index("ix_documents_filing_date", "documents", ["filing_date"])
    op.create_index("ix_documents_checksum", "documents", ["checksum"])

    op.create_table(
        "document_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("doc_id", sa.String(length=36), nullable=False),
        sa.Column("bucket", sa.String(length=63), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_document_files_doc_id", "document_files", ["doc_id"])
    op.create_index("ix_document_files_checksum", "document_files", ["checksum"])


def downgrade() -> None:
    op.drop_index("ix_document_files_checksum", table_name="document_files")
    op.drop_index("ix_document_files_doc_id", table_name="document_files")
    op.drop_table("document_files")

    op.drop_index("ix_documents_checksum", table_name="documents")
    op.drop_index("ix_documents_filing_date", table_name="documents")
    op.drop_index("ix_documents_fiscal_year", table_name="documents")
    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_index("ix_documents_ticker", table_name="documents")
    op.drop_table("documents")

    op.drop_table("companies")

