"""Add data-quality columns to vehicles (valid/quarantined/invalid + audit)

Revision ID: a1b2c3d4e5f6
Revises: 3f7a2b1c85d4
Create Date: 2026-08-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3f7a2b1c85d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vehicles', sa.Column('quality_status', sa.String(length=20), nullable=True))
    op.add_column('vehicles', sa.Column('quality_reasons', sa.JSON(), nullable=True))
    op.add_column('vehicles', sa.Column('quality_checked_at', sa.DateTime(), nullable=True))
    op.add_column('vehicles', sa.Column('normalized_brand', sa.String(length=100), nullable=True))
    op.add_column('vehicles', sa.Column('normalization_confidence', sa.Float(), nullable=True))
    op.create_index('idx_vehicles_quality_status', 'vehicles', ['quality_status'])
    op.create_index('idx_vehicles_normalized_brand', 'vehicles', ['normalized_brand'])
    op.execute("UPDATE vehicles SET quality_status = 'valid' WHERE quality_status IS NULL")


def downgrade() -> None:
    op.drop_index('idx_vehicles_normalized_brand', table_name='vehicles')
    op.drop_index('idx_vehicles_quality_status', table_name='vehicles')
    op.drop_column('vehicles', 'normalization_confidence')
    op.drop_column('vehicles', 'normalized_brand')
    op.drop_column('vehicles', 'quality_checked_at')
    op.drop_column('vehicles', 'quality_reasons')
    op.drop_column('vehicles', 'quality_status')
