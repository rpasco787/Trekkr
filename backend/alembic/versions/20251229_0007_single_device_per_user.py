"""Single device per user

Revision ID: 20251229_0007
Revises: 20251227_0006
Create Date: 2025-12-29

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '20251229_0007'
down_revision = '20251227_0006'
branch_labels = None
depends_on = None


def upgrade():
    """Add unique constraint on user_id to enforce one device per user."""
    op.create_unique_constraint(
        'uq_devices_user_id',
        'devices',
        ['user_id']
    )


def downgrade():
    """Remove unique constraint to allow multiple devices per user."""
    op.drop_constraint(
        'uq_devices_user_id',
        'devices',
        type_='unique'
    )
