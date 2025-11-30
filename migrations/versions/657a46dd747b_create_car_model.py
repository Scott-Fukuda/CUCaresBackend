"""create car model

Revision ID: 657a46dd747b
Revises: 1a2b3c4d5e6f
Create Date: 2025-10-31 21:36:49.346173

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '657a46dd747b'
down_revision = 'cb09c83d0f8f' 
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('car',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('color', sa.String(), nullable=True),
    sa.Column('model', sa.String(), nullable=True),
    sa.Column('seats', sa.Integer(), nullable=False),
    sa.Column('license_plate', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('car')