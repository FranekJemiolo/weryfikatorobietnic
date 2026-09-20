"""add_interpellations_committees_amendments_rcl_and_factchecks

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-20 23:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Tabela interpellations (interpelacje poselskie)
    op.create_table(
        "interpellations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mp_id", sa.Integer(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("receipt_date", sa.DateTime(), nullable=False),
        sa.Column("is_answered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(
            ["mp_id"],
            ["mps.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_interpellations_mp_id"),
        "interpellations",
        ["mp_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interpellations_receipt_date"),
        "interpellations",
        ["receipt_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interpellations_is_answered"),
        "interpellations",
        ["is_answered"],
        unique=False,
    )

    # 2. Tabela committees (komisje sejmowe)
    op.create_table(
        "committees",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. Tabela committee_sittings (posiedzenia komisji)
    op.create_table(
        "committee_sittings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("committee_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["committee_id"],
            ["committees.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_committee_sittings_committee_id"),
        "committee_sittings",
        ["committee_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_committee_sittings_date"),
        "committee_sittings",
        ["date"],
        unique=False,
    )

    # 4. Tabela bill_amendments (poprawki w komisjach / plenarne)
    op.create_table(
        "bill_amendments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bill_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("mp_id", sa.Integer(), nullable=True),
        sa.Column("text_content", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_accepted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("article_reference", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(
            ["bill_id"],
            ["bills.id"],
        ),
        sa.ForeignKeyConstraint(
            ["mp_id"],
            ["mps.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bill_amendments_bill_id"),
        "bill_amendments",
        ["bill_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bill_amendments_mp_id"),
        "bill_amendments",
        ["mp_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bill_amendments_is_accepted"),
        "bill_amendments",
        ["is_accepted"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bill_amendments_article_reference"),
        "bill_amendments",
        ["article_reference"],
        unique=False,
    )

    # 5. Tabela pre_legislative_processes (etap w RCL)
    op.create_table(
        "pre_legislative_processes",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("rcl_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("stage", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("institution", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_date", sa.DateTime(), nullable=True),
        sa.Column("updated_date", sa.DateTime(), nullable=True),
        sa.Column("consultation_end_date", sa.DateTime(), nullable=True),
        sa.Column("bill_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(
            ["bill_id"],
            ["bills.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pre_legislative_processes_rcl_id"),
        "pre_legislative_processes",
        ["rcl_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pre_legislative_processes_stage"),
        "pre_legislative_processes",
        ["stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pre_legislative_processes_created_date"),
        "pre_legislative_processes",
        ["created_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pre_legislative_processes_bill_id"),
        "pre_legislative_processes",
        ["bill_id"],
        unique=False,
    )

    # 6. Pole external_factchecks w promises
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.add_column(
        "promises",
        sa.Column("external_factchecks", json_type, nullable=False, server_default=sa.text("'[]'")),
    )

    # 7. Pole requires_re_evaluation w llm_evaluations
    op.add_column(
        "llm_evaluations",
        sa.Column(
            "requires_re_evaluation", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.create_index(
        op.f("ix_llm_evaluations_requires_re_evaluation"),
        "llm_evaluations",
        ["requires_re_evaluation"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_llm_evaluations_requires_re_evaluation"), table_name="llm_evaluations")
    op.drop_column("llm_evaluations", "requires_re_evaluation")
    op.drop_column("promises", "external_factchecks")

    op.drop_index(
        op.f("ix_pre_legislative_processes_bill_id"), table_name="pre_legislative_processes"
    )
    op.drop_index(
        op.f("ix_pre_legislative_processes_created_date"), table_name="pre_legislative_processes"
    )
    op.drop_index(
        op.f("ix_pre_legislative_processes_stage"), table_name="pre_legislative_processes"
    )
    op.drop_index(
        op.f("ix_pre_legislative_processes_rcl_id"), table_name="pre_legislative_processes"
    )
    op.drop_table("pre_legislative_processes")

    op.drop_index(op.f("ix_bill_amendments_article_reference"), table_name="bill_amendments")
    op.drop_index(op.f("ix_bill_amendments_is_accepted"), table_name="bill_amendments")
    op.drop_index(op.f("ix_bill_amendments_mp_id"), table_name="bill_amendments")
    op.drop_index(op.f("ix_bill_amendments_bill_id"), table_name="bill_amendments")
    op.drop_table("bill_amendments")

    op.drop_index(op.f("ix_committee_sittings_date"), table_name="committee_sittings")
    op.drop_index(op.f("ix_committee_sittings_committee_id"), table_name="committee_sittings")
    op.drop_table("committee_sittings")

    op.drop_table("committees")

    op.drop_index(op.f("ix_interpellations_is_answered"), table_name="interpellations")
    op.drop_index(op.f("ix_interpellations_receipt_date"), table_name="interpellations")
    op.drop_index(op.f("ix_interpellations_mp_id"), table_name="interpellations")
    op.drop_table("interpellations")
