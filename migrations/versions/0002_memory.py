"""Versioned memory, source documents and local full-text search.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("project_id", sa.String, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("relative_path", sa.String, nullable=False),
        sa.Column("content_hash", sa.String, nullable=False),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("scope", sa.String, nullable=False),
        sa.Column("indexed_at", sa.String, nullable=False),
        sa.UniqueConstraint("project_id", "relative_path"),
    )
    op.create_table(
        "memory_records",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("project_id", sa.String, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("scope", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("source_kind", sa.String, nullable=False),
        sa.Column("source_document_id", sa.String, sa.ForeignKey("source_documents.id")),
        sa.Column("current_version", sa.Integer, nullable=False),
        sa.Column("visibility", sa.String, nullable=False),
        sa.Column("deleted_at", sa.String),
        sa.UniqueConstraint("source_document_id"),
    )
    op.create_table(
        "memory_versions",
        sa.Column("record_id", sa.String, sa.ForeignKey("memory_records.id"), primary_key=True),
        sa.Column("version", sa.Integer, primary_key=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("source_refs", sa.Text, nullable=False),
        sa.Column("valid_for", sa.Text, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("actor_id", sa.String, nullable=False),
        sa.Column("reason", sa.String, nullable=False),
    )
    op.create_table(
        "relations",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("project_id", sa.String, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("source_id", sa.String, sa.ForeignKey("memory_records.id"), nullable=False),
        sa.Column("target_id", sa.String, sa.ForeignKey("memory_records.id"), nullable=False),
        sa.Column("relation_type", sa.String, nullable=False),
        sa.Column("origin", sa.String, nullable=False),
    )
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("project_id", sa.String, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("operation", sa.String, nullable=False),
        sa.Column("target_id", sa.String, nullable=False),
        sa.Column("target_version", sa.Integer, nullable=False),
        sa.Column("reason", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
    )
    op.execute("CREATE VIRTUAL TABLE memory_fts USING fts5(record_id UNINDEXED, title, body)")


def downgrade() -> None:
    op.execute("DROP TABLE memory_fts")
    for table in ("audit_entries", "relations", "memory_versions", "memory_records", "source_documents"):
        op.drop_table(table)
