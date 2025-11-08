"""Add ApprovedEmail table

Revision ID: c8f73ecd751c
Revises: 3267b50fa1d8
Create Date: 2025-09-10 00:45:37.819640

"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401
from sqlalchemy.dialects import postgresql  # noqa: F401

# revision identifiers, used by Alembic.
revision = 'c8f73ecd751c'
down_revision = '3267b50fa1d8'
branch_labels = None
depends_on = None


def upgrade():
    """This migration has been superseded by revision 3267b50fa1d8."""
    pass


def downgrade():
    """No-op to mirror upgrade() change."""
    pass
