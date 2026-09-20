"""add_push_subscribers_subscriptions_and_webhooks

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-20 23:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Tabela push_subscribers (subskrybenci PWA Web Push bez PII)
    op.create_table(
        "push_subscribers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("endpoint_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("p256dh_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("auth_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_push_subscribers_endpoint_url"), "push_subscribers", ["endpoint_url"], unique=True
    )

    # 2. Tabela citizen_subscriptions (subskrypcje obietnic, posłów, kategorii)
    op.create_table(
        "citizen_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscriber_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("target_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["subscriber_id"], ["push_subscribers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_citizen_subscriptions_subscriber_id"),
        "citizen_subscriptions",
        ["subscriber_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_citizen_subscriptions_target_type"),
        "citizen_subscriptions",
        ["target_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_citizen_subscriptions_target_id"),
        "citizen_subscriptions",
        ["target_id"],
        unique=False,
    )

    # 3. Tabela ngo_webhooks (webhooki dla NGO i dziennikarzy z HMAC)
    op.create_table(
        "ngo_webhooks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("target_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("secret_token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ngo_webhooks_organization_name"),
        "ngo_webhooks",
        ["organization_name"],
        unique=False,
    )
    op.create_index(op.f("ix_ngo_webhooks_is_active"), "ngo_webhooks", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ngo_webhooks_is_active"), table_name="ngo_webhooks")
    op.drop_index(op.f("ix_ngo_webhooks_organization_name"), table_name="ngo_webhooks")
    op.drop_table("ngo_webhooks")

    op.drop_index(op.f("ix_citizen_subscriptions_target_id"), table_name="citizen_subscriptions")
    op.drop_index(op.f("ix_citizen_subscriptions_target_type"), table_name="citizen_subscriptions")
    op.drop_index(
        op.f("ix_citizen_subscriptions_subscriber_id"), table_name="citizen_subscriptions"
    )
    op.drop_table("citizen_subscriptions")

    op.drop_index(op.f("ix_push_subscribers_endpoint_url"), table_name="push_subscribers")
    op.drop_table("push_subscribers")
