"""Add CASCADE constraints for passive deletes

Revision ID: 9abf18dd9dbc
Revises: f7786616235b
Create Date: 2026-01-23 14:42:21.552373

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9abf18dd9dbc'
down_revision = 'f7786616235b'
branch_labels = None
depends_on = None


def upgrade():
    # Add CASCADE to existing foreign keys
    op.execute('ALTER TABLE opportunity DROP CONSTRAINT opportunity_multiopp_id_fkey')
    op.execute('ALTER TABLE opportunity ADD CONSTRAINT opportunity_multiopp_id_fkey FOREIGN KEY (multiopp_id) REFERENCES multi_opportunity(id) ON DELETE CASCADE')
    
    op.execute('ALTER TABLE ride DROP CONSTRAINT ride_carpool_id_fkey')
    op.execute('ALTER TABLE ride ADD CONSTRAINT ride_carpool_id_fkey FOREIGN KEY (carpool_id) REFERENCES carpool(id) ON DELETE CASCADE')
    
    op.execute('ALTER TABLE ride_riders DROP CONSTRAINT ride_riders_ride_id_fkey')
    op.execute('ALTER TABLE ride_riders ADD CONSTRAINT ride_riders_ride_id_fkey FOREIGN KEY (ride_id) REFERENCES ride(id) ON DELETE CASCADE')

def downgrade():
    # Remove CASCADE (revert to RESTRICT)
    op.execute('ALTER TABLE opportunity DROP CONSTRAINT opportunity_multiopp_id_fkey')
    op.execute('ALTER TABLE opportunity ADD CONSTRAINT opportunity_multiopp_id_fkey FOREIGN KEY (multiopp_id) REFERENCES multi_opportunity(id)')
    
    op.execute('ALTER TABLE ride DROP CONSTRAINT ride_carpool_id_fkey')
    op.execute('ALTER TABLE ride ADD CONSTRAINT ride_carpool_id_fkey FOREIGN KEY (carpool_id) REFERENCES carpool(id)')
    
    op.execute('ALTER TABLE ride_riders DROP CONSTRAINT ride_riders_ride_id_fkey')
    op.execute('ALTER TABLE ride_riders ADD CONSTRAINT ride_riders_ride_id_fkey FOREIGN KEY (ride_id) REFERENCES ride(id)')