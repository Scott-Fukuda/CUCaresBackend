"""add carpool ride and ride_riders tables

Revision ID: 1a2b3c4d5e6f
Revises: cb09c83d0f8f
Create Date: 2025-11-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = 'cb09c83d0f8f'
branch_labels = None
depends_on = None


def upgrade():
    # ### Add carpool tables ###
    op.create_table('carpool',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('opportunity_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunity.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('ride',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('carpool_id', sa.Integer(), nullable=False),
    sa.Column('driver_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['carpool_id'], ['carpool.id'], ),
    sa.ForeignKeyConstraint(['driver_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('ride_riders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ride_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('pickup_location', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['ride_id'], ['ride.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Add allow_carpool field to opportunity
    with op.batch_alter_table('opportunity', schema=None) as batch_op:
        batch_op.add_column(sa.Column('allow_carpool', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('opportunity', schema=None) as batch_op:
        batch_op.drop_column('allow_carpool')
    
    op.drop_table('ride_riders')
    op.drop_table('ride')
    op.drop_table('carpool')