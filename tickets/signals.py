# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Event, Seat
import string

# Create student profile automatically



