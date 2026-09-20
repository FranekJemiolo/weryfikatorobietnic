"""add_senate_isap_affiliations_and_approval

Revision ID: a1b2c3d4e5f6
Revises: 960864ff1906
Create Date: 2026-09-20 22:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "960864ff1906"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Tabela mp_club_affiliations (transfery polityczne)
    op.create_table(
        "mp_club_affiliations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mp_id", sa.Integer(), nullable=False),
        sa.Column("club_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["mp_id"],
            ["mps.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mp_club_affiliations_mp_id"),
        "mp_club_affiliations",
        ["mp_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mp_club_affiliations_club_name"),
        "mp_club_affiliations",
        ["club_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mp_club_affiliations_start_date"),
        "mp_club_affiliations",
        ["start_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mp_club_affiliations_end_date"),
        "mp_club_affiliations",
        ["end_date"],
        unique=False,
    )

    # 2. Tabela rss_feed_items
    op.create_table(
        "rss_feed_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("feed_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("link", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("summary", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("guid", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link"),
    )
    op.create_index(
        op.f("ix_rss_feed_items_source_name"), "rss_feed_items", ["source_name"], unique=False
    )
    op.create_index(
        op.f("ix_rss_feed_items_feed_url"), "rss_feed_items", ["feed_url"], unique=False
    )
    op.create_index(op.f("ix_rss_feed_items_title"), "rss_feed_items", ["title"], unique=False)
    op.create_index(op.f("ix_rss_feed_items_link"), "rss_feed_items", ["link"], unique=True)
    op.create_index(
        op.f("ix_rss_feed_items_published_at"), "rss_feed_items", ["published_at"], unique=False
    )
    op.create_index(op.f("ix_rss_feed_items_guid"), "rss_feed_items", ["guid"], unique=False)

    # 3. Rozszerzenie tabeli bills
    op.add_column(
        "bills", sa.Column("senate_status", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
    )
    op.create_index(op.f("ix_bills_senate_status"), "bills", ["senate_status"], unique=False)
    op.add_column("bills", sa.Column("president_signature_date", sa.DateTime(), nullable=True))
    op.create_index(
        op.f("ix_bills_president_signature_date"),
        "bills",
        ["president_signature_date"],
        unique=False,
    )
    op.add_column(
        "bills", sa.Column("isap_publication_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
    )
    op.create_index(
        op.f("ix_bills_isap_publication_id"), "bills", ["isap_publication_id"], unique=False
    )

    # 4. Rozszerzenie tabeli llm_evaluations
    op.add_column(
        "llm_evaluations",
        sa.Column("is_approved_by_human", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index(
        op.f("ix_llm_evaluations_is_approved_by_human"),
        "llm_evaluations",
        ["is_approved_by_human"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_llm_evaluations_is_approved_by_human"), table_name="llm_evaluations")
    op.drop_column("llm_evaluations", "is_approved_by_human")

    op.drop_index(op.f("ix_bills_isap_publication_id"), table_name="bills")
    op.drop_column("bills", "isap_publication_id")
    op.drop_index(op.f("ix_bills_president_signature_date"), table_name="bills")
    op.drop_column("bills", "president_signature_date")
    op.drop_index(op.f("ix_bills_senate_status"), table_name="bills")
    op.drop_column("bills", "senate_status")

    op.drop_table("rss_feed_items")
    op.drop_table("mp_club_affiliations")
