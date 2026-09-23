"""add_hnsw_index_on_bill_articles

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-23 00:01:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Upewnienie się, że rozszerzenie vector jest aktywne w PostgreSQL
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Indeks HNSW (Hierarchical Navigable Small World) dla wektorów embeddingu (1536 wymiarów)
    # Złożoność wyszukiwania O(log N) zamiast pełnego skanowania O(N).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bill_articles_embedding_hnsw
        ON bill_articles
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_bill_articles_embedding_hnsw;")
