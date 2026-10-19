"""
Migración inicial: crear tablas del sistema de auditoría Merkle.

Revision ID: 001
Revises: --
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_models"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === MerkleBatch ===
    op.create_table(
        "merkle_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_number", sa.Integer(), nullable=False, unique=True, autoincrement=True),
        sa.Column("leaf_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("merkle_root", sa.String(64), nullable=True),
        sa.Column("prev_batch_root", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # === LogEntry ===
    op.create_table(
        "log_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_app", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False, server_default="info"),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("merkle_batches.id"), nullable=True),
        sa.Column("leaf_index", sa.Integer(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_log_entries_source_app", "log_entries", ["source_app"])
    op.create_index("ix_log_entries_event_type", "log_entries", ["event_type"])
    op.create_index("ix_log_entries_severity", "log_entries", ["severity"])
    op.create_index("ix_log_entries_received_at", "log_entries", ["received_at"])
    op.create_index("ix_log_entries_content_hash", "log_entries", ["content_hash"])
    op.create_index("ix_log_entries_batch_id", "log_entries", ["batch_id"])

    # === MerkleNode ===
    op.create_table(
        "merkle_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("merkle_batches.id"), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("hash_value", sa.String(64), nullable=False),
        sa.Column("left_child_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("merkle_nodes.id"), nullable=True),
        sa.Column("right_child_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("merkle_nodes.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_merkle_nodes_batch_level", "merkle_nodes", ["batch_id", "level"])
    op.create_index("ix_merkle_nodes_batch_level_pos", "merkle_nodes", ["batch_id", "level", "position"])

    # === AnchorRecord ===
    op.create_table(
        "anchor_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("merkle_batches.id"), nullable=False),
        sa.Column("merkle_root", sa.String(64), nullable=False),
        sa.Column("anchor_type", sa.String(50), nullable=False),
        sa.Column("tx_hash", sa.String(128), nullable=True),
        sa.Column("block_number", sa.Integer(), nullable=True),
        sa.Column("network", sa.String(50), nullable=True),
        sa.Column("anchor_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("anchor_records")
    op.drop_table("merkle_nodes")
    op.drop_table("log_entries")
    op.drop_table("merkle_batches")
