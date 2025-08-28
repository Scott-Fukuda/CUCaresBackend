#!/usr/bin/env python3
"""
Database setup script for PostgreSQL migration
"""
import os
from app import app, db
from db import User, Organization, Opportunity, UserOpportunity, Friendship

def setup_database():
    """Initialize the database and create tables"""
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✅ Database tables created successfully!")
        
        # Check if we have any data
        user_count = User.query.count()
        org_count = Organization.query.count()
        opp_count = Opportunity.query.count()
        
        print(f"📊 Current database stats:")
        print(f"   Users: {user_count}")
        print(f"   Organizations: {org_count}")
        print(f"   Opportunities: {opp_count}")
        
        if user_count == 0:
            print("💡 Database is empty - ready for new data!")

if __name__ == "__main__":
    setup_database()
