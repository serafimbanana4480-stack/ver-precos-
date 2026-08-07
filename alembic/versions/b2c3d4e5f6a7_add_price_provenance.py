"""Add raw price provenance and auction bid observations.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-01

The columns are nullable so legacy rows remain readable during the migration.
New ingestion must populate the provenance contract before a row is eligible
for retail valuation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("vehicles", sa.Column("price_raw", sa.Text(), nullable=True))
    op.add_column("vehicles", sa.Column("price_observed_value", sa.Float(), nullable=True))
    op.add_column("vehicles", sa.Column("currency", sa.String(length=3), nullable=True))
    op.add_column("vehicles", sa.Column("price_kind", sa.String(length=32), nullable=True))
    op.add_column("vehicles", sa.Column("price_evidence", sa.Text(), nullable=True))
    op.add_column("vehicles", sa.Column("price_rejection_reason", sa.Text(), nullable=True))
    op.add_column("auction_transactions", sa.Column("current_bid", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("auction_transactions", "current_bid")
    op.drop_column("vehicles", "price_rejection_reason")
    op.drop_column("vehicles", "price_evidence")
    op.drop_column("vehicles", "price_kind")
    op.drop_column("vehicles", "currency")
    op.drop_column("vehicles", "price_observed_value")
    op.drop_column("vehicles", "price_raw")
