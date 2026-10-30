"""Add price_selector column and allow the playwright_js source

Revision ID: 0002_playwright_source
Revises: 0001_initial
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_playwright_source"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCES = "('books_toscrape', 'coingecko', 'playwright_js')"


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("price_selector", sa.String(length=255), nullable=True),
    )
    # SQLite cannot alter constraints in place -> batch (table rebuild)
    with op.batch_alter_table("products") as batch:
        batch.drop_constraint("ck_products_source", type_="check")
        batch.create_check_constraint(
            "ck_products_source", f"source IN {_SOURCES}"
        )


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.drop_constraint("ck_products_source", type_="check")
        batch.create_check_constraint(
            "ck_products_source", "source IN ('books_toscrape', 'coingecko')"
        )
        batch.drop_column("price_selector")
