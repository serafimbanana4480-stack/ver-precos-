"""Add auction_transactions table for real transaction prices

Revision ID: 3f7a2b1c85d4
Revises: 8727b491756e
Create Date: 2026-05-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f7a2b1c85d4'
down_revision: Union[str, None] = '8727b491756e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'auction_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.Enum('OLX', 'STANDVIRTUAL', 'AUTOSAPO', 'CUSTOJUSTO', 'VPAUTO', 'LEILOSOC', 'MANHEIM', 'AUTOROLA', 'BCA', name='source'), nullable=False),
        sa.Column('source_id', sa.String(length=100), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('vehicle_type', sa.Enum('carros', 'motos', name='vehicletype'), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=200), nullable=True),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('km', sa.Integer(), nullable=True),
        sa.Column('horsepower', sa.Integer(), nullable=True),
        sa.Column('engine_size', sa.Integer(), nullable=True),
        sa.Column('fuel_type', sa.Enum('GASOLINE', 'DIESEL', 'ELECTRIC', 'HYBRID', 'GPL', 'GAS', name='fueltype'), nullable=True),
        sa.Column('transmission', sa.Enum('MANUAL', 'AUTOMATIC', 'SEMI_AUTOMATIC', name='transmission'), nullable=True),
        sa.Column('color', sa.String(length=50), nullable=True),
        sa.Column('location', sa.String(length=200), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('auction_type', sa.String(length=50), nullable=True),
        sa.Column('auction_date', sa.DateTime(), nullable=True),
        sa.Column('lot_number', sa.String(length=50), nullable=True),
        sa.Column('adjudication_price', sa.Float(), nullable=False),
        sa.Column('reserve_price', sa.Float(), nullable=True),
        sa.Column('starting_price', sa.Float(), nullable=True),
        sa.Column('retail_price', sa.Float(), nullable=True),
        sa.Column('condition_grade', sa.String(length=10), nullable=True),
        sa.Column('has_damage', sa.Boolean(), nullable=True),
        sa.Column('damage_notes', sa.Text(), nullable=True),
        sa.Column('inspection_report_url', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('images', sa.JSON(), nullable=True),
        sa.Column('seller_type', sa.String(length=50), nullable=True),
        sa.Column('seller_name', sa.String(length=200), nullable=True),
        sa.Column('scraped_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('matched_vehicle_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['matched_vehicle_id'], ['vehicles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id')
    )
    op.create_index('ix_auction_transactions_source', 'auction_transactions', ['source'], unique=False)
    op.create_index('ix_auction_transactions_adjudication_price', 'auction_transactions', ['adjudication_price'], unique=False)
    op.create_index('ix_auction_transactions_auction_date', 'auction_transactions', ['auction_date'], unique=False)
    op.create_index('ix_auction_transactions_brand', 'auction_transactions', ['brand'], unique=False)
    op.create_index('ix_auction_transactions_is_active', 'auction_transactions', ['is_active'], unique=False)
    op.create_index('ix_auction_transactions_matched_vehicle_id', 'auction_transactions', ['matched_vehicle_id'], unique=False)
    op.create_index('ix_auction_transactions_model', 'auction_transactions', ['model'], unique=False)
    op.create_index('ix_auction_transactions_source_1', 'auction_transactions', ['source'], unique=False)
    op.create_index('ix_auction_transactions_vehicle_type', 'auction_transactions', ['vehicle_type'], unique=False)
    op.create_index('ix_auction_transactions_year', 'auction_transactions', ['year'], unique=False)
    op.create_index('idx_auction_brand_model', 'auction_transactions', ['brand', 'model'], unique=False)
    op.create_index('idx_auction_price_date', 'auction_transactions', ['adjudication_price', 'auction_date'], unique=False)
    op.create_index('idx_auction_source_id', 'auction_transactions', ['source', 'source_id'], unique=True)
    op.create_index('idx_auction_year_km', 'auction_transactions', ['year', 'km'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_auction_year_km', table_name='auction_transactions')
    op.drop_index('idx_auction_source_id', table_name='auction_transactions')
    op.drop_index('idx_auction_price_date', table_name='auction_transactions')
    op.drop_index('idx_auction_brand_model', table_name='auction_transactions')
    op.drop_index('ix_auction_transactions_year', table_name='auction_transactions')
    op.drop_index('ix_auction_transactions_vehicle_type', table_name='auction_transactions')
    op.drop_index('ix_auction_transactions_source_1', table_name='auction_transactions')
    op.drop_index('ix_auction_transactions_model', table_name='auction_transactions')
    op.drop_index('ix_auction_transactions_matched_vehicle_id', table_name='auction_transactions')
    op.drop_index('ix_auction_transactions_is_active', table_name='auction_transactions')
    op.drop_index('ix_auction_transactions_brand', table_name='auction_transactions')
    op.drop_index('ix_auction_transactions_auction_date', table_name='auction_transactions')
    op.drop_index('ix_auction_transactions_adjudication_price', table_name='auction_transactions')
    op.drop_index('ix_auction_transactions_source', table_name='auction_transactions')
    op.drop_table('auction_transactions')