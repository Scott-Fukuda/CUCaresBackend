"""add new field carpool_waiver_signed to User

Revision ID: fc00097faa88
Revises: f7b61f73faeb
Create Date: 2025-10-13 20:56:39.717311

"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision = 'fc00097faa88'
down_revision = 'f7b61f73faeb'
branch_labels = None
depends_on = None


def upgrade():
    """This legacy migration is superseded by 3267b50fa1d8."""
    pass


def downgrade():
    """No-op to mirror upgrade() change."""
    pass
