# migrations/versions/xxxx_create_events_table.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers:
revision = "0001_create_events"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("ua", sa.Text(), nullable=True),
        sa.Column("path", sa.String(length=512), nullable=True),
        sa.Column("reason", sa.String(length=64), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("severity", sa.Integer(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_events_ts", "events", ["ts"])
    op.create_index("ix_events_ip_ts", "events", ["ip_hash", "ts"], unique=False)
    op.create_index("ix_events_reason_ts", "events", ["reason", "ts"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_events_reason_ts", table_name="events")
    op.drop_index("ix_events_ip_ts", table_name="events")
    op.drop_index("ix_events_ts", table_name="events")
    op.drop_table("events")