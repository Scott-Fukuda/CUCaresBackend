"""Add Waiver table

Revision ID: f7b61f73faeb
Revises: c8f73ecd751c
Create Date: 2025-10-13 16:13:11.747763

"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision = 'f7b61f73faeb'
down_revision = 'c8f73ecd751c'
branch_labels = None
depends_on = None


def upgrade():
    """This legacy migration is superseded by 3267b50fa1d8."""
    pass


def downgrade():
    """No-op to mirror upgrade() change."""
    pass
