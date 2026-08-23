"""Add indexes for the canonical valuation and opportunity queries.

These indexes match the equality/freshness/ranking predicates used by the
canonical FastAPI routes and DealFinder.  They are deliberately explicit so
SQLite and PostgreSQL receive the same schema change.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_vehicles_estimated_value",
        "vehicles",
        ["estimated_value"],
    )
    op.create_index(
        "idx_vehicle_active_market_score",
        "vehicles",
        ["is_active", "price_kind", "currency", "quality_status", "last_seen", "deal_score"],
    )
    op.create_index(
        "idx_vehicle_active_publishable_score",
        "vehicles",
        [
            "is_active", "profit_is_publishable", "price_kind", "currency",
            "quality_status", "last_seen", "deal_score",
        ],
    )
    op.create_index(
        "idx_vehicle_market_identity",
        "vehicles",
        ["brand", "model", "year", "vehicle_type", "price_kind", "currency", "quality_status"],
    )


def downgrade() -> None:
    op.drop_index("idx_vehicle_market_identity", table_name="vehicles")
    op.drop_index("idx_vehicle_active_publishable_score", table_name="vehicles")
    op.drop_index("idx_vehicle_active_market_score", table_name="vehicles")
    op.drop_index("ix_vehicles_estimated_value", table_name="vehicles")
