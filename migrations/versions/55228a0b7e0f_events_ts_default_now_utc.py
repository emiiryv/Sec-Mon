"""events.ts default now utc

Revision ID: 55228a0b7e0f
Revises: 0001_create_events
Create Date: 2025-10-29 12:07:32.678646+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '55228a0b7e0f'
down_revision: Union[str, Sequence[str], None] = '0001_create_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Var olan null'ları doldur (olasılık düşük ama sağlam kalsın)
    op.execute("UPDATE events SET ts = NOW() AT TIME ZONE 'UTC' WHERE ts IS NULL;")

    # Kolonu timestamptz'e çevirip default ver (PG tarafında)
    op.alter_column(
        "events",
        "ts",
        type_=sa.TIMESTAMP(timezone=True),
        server_default=sa.text("NOW() AT TIME ZONE 'UTC'"),
        existing_nullable=False,
    )

def downgrade():
    op.alter_column(
        "events",
        "ts",
        type_=sa.TIMESTAMP(timezone=False),
        server_default=None,
        existing_nullable=False,
    )