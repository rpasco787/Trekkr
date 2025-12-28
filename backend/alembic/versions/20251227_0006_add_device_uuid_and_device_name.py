"""add device_uuid and device_name to devices table

Revision ID: 20251227_0006
Revises: 20251226_0005
Create Date: 2025-12-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251227_0006'
down_revision = '20251226_0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add device_uuid and device_name columns to devices table
    op.add_column('devices', sa.Column('device_uuid', sa.String(length=255), nullable=True))
    op.add_column('devices', sa.Column('device_name', sa.String(length=255), nullable=True))

    # Create unique index on device_uuid
    op.create_index('ix_devices_device_uuid', 'devices', ['device_uuid'], unique=True)

    # For existing rows, generate a UUID (in production, this would need data migration)
    # For now, we'll allow NULL temporarily
    # In a real migration, you'd need to backfill UUIDs for existing devices


def downgrade() -> None:
    # Drop the index and columns
    op.drop_index('ix_devices_device_uuid', table_name='devices')
    op.drop_column('devices', 'device_name')
    op.drop_column('devices', 'device_uuid')
