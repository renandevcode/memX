"""Initial local persistence schema.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("root", sa.String, nullable=False, unique=True),
        sa.Column("repo_identity", sa.String, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("project_id", sa.String, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("objective", sa.Text, nullable=False),
        sa.Column("acceptance", sa.Text, nullable=False),
        sa.Column("scope", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("project_id", sa.String, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("task_id", sa.String, sa.ForeignKey("tasks.id")),
        sa.Column("host", sa.String, nullable=False),
        sa.Column("agent_label", sa.String, nullable=False),
        sa.Column("model_label", sa.String),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("started_at", sa.String, nullable=False),
        sa.Column("ended_at", sa.String),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("project_id", sa.String, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("session_id", sa.String, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("task_id", sa.String, sa.ForeignKey("tasks.id")),
        sa.Column("idempotency_key", sa.String, nullable=False),
        sa.Column("fingerprint", sa.String, nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("captured_at", sa.String, nullable=False),
        sa.UniqueConstraint("session_id", "idempotency_key"),
        sa.UniqueConstraint("session_id", "sequence"),
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("project_id", sa.String, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("artifact_ref", sa.String, nullable=False),
        sa.Column("content_hash", sa.String, nullable=False),
        sa.Column("checkout_ref", sa.Text, nullable=False),
        sa.Column("verification_status", sa.String, nullable=False),
        sa.Column("observed_at", sa.String, nullable=False),
    )
    op.create_table(
        "checkpoints",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("project_id", sa.String, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("task_id", sa.String, sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("task_version", sa.Integer, nullable=False),
        sa.Column("session_id", sa.String, sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("idempotency_key", sa.String, nullable=False),
        sa.Column("fingerprint", sa.String, nullable=False),
        sa.Column("completed", sa.Text, nullable=False),
        sa.Column("pending", sa.Text, nullable=False),
        sa.Column("blockers", sa.Text, nullable=False),
        sa.Column("next_action", sa.Text, nullable=False),
        sa.Column("changed_paths", sa.Text, nullable=False),
        sa.Column("evidence_refs", sa.Text, nullable=False),
        sa.Column("checkout_ref", sa.Text, nullable=False),
        sa.Column("event_watermark", sa.Integer, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.UniqueConstraint("task_id", "idempotency_key"),
    )
    op.create_table(
        "handoffs",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("project_id", sa.String, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("task_id", sa.String, sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("checkpoint_id", sa.String, sa.ForeignKey("checkpoints.id"), nullable=False),
        sa.Column("idempotency_key", sa.String, nullable=False),
        sa.Column("fingerprint", sa.String, nullable=False),
        sa.Column("state", sa.String, nullable=False),
        sa.Column("claimed_by", sa.String),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.String, nullable=False),
        sa.UniqueConstraint("task_id", "idempotency_key"),
    )


def downgrade() -> None:
    for table in ("handoffs", "checkpoints", "evidence", "events", "sessions", "tasks", "projects"):
        op.drop_table(table)
