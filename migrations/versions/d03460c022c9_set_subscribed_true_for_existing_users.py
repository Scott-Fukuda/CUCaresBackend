"""set subscribed true for existing users

Revision ID: d03460c022c9
Revises: 4de903677c97
Create Date: 2026-03-14 23:32:22.702593

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd03460c022c9'
down_revision = '4de903677c97'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('UPDATE "user" SET subscribed = TRUE')
    

def downgrade():
    pass
