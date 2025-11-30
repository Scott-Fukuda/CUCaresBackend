"""Shared imports for the entire application"""
from app import app, db
from db import Opportunity, User, Carpool, Car, Ride, RideRider

__all__ = ['app', 'db', 'Opportunity', 'User', 'Carpool', 'Car', 'Ride', 'RideRider']