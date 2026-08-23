"""Add single-column indexes used by valuation and deal filters."""
from typing import Sequence, Union

from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for name, column in (
        ("ix_vehicles_comparables_count", "comparables_count"),
        ("ix_vehicles_credible_profit", "credible_profit"),
        ("ix_vehicles_net_profit", "net_profit"),
        ("ix_vehicles_profit_is_publishable", "profit_is_publishable"),
        ("ix_vehicles_valuation_confidence", "valuation_confidence"),
    ):
        op.create_index(name, "vehicles", [column])


def downgrade() -> None:
    for name in (
        "ix_vehicles_valuation_confidence",
        "ix_vehicles_profit_is_publishable",
        "ix_vehicles_net_profit",
        "ix_vehicles_credible_profit",
        "ix_vehicles_comparables_count",
    ):
        op.drop_index(name, table_name="vehicles")
