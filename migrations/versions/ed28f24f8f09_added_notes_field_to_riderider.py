"""added notes field to ride_riders

Revision ID: ed28f24f8f09
Revises: 657a46dd747b
Create Date: 2025-11-06 16:08:20.318238

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed28f24f8f09'
down_revision = '657a46dd747b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ride_riders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('ride_riders', schema=None) as batch_op:
        batch_op.drop_column('notes')