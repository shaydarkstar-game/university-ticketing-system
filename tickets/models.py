# ==========================================
# IMPORTS
# ==========================================

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from datetime import datetime, date
from django.utils.timezone import make_aware
from django.utils import timezone
import uuid
import string


# ==========================================
# USER MODEL
# ==========================================

class User(AbstractUser):

    UNIVERSITY_ROLES = [
        ('student', 'Student'),
        ('staff', 'Staff'),
        ('admin', 'Admin'),
    ]

    university_id = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True)

    role = models.CharField(
        max_length=10,
        choices=UNIVERSITY_ROLES,
        default='student'
    )

    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        default='profile_pics/default.png'
    )

    def __str__(self):
        return f"{self.username} ({self.role})"


# ==========================================
# CAMPUS
# ==========================================

class Campus(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


# ==========================================
# CATEGORY
# ==========================================

class EventCategory(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# ==========================================
# EVENT MODEL
# ==========================================

class Event(models.Model):

    image = models.ImageField(upload_to='event_images/', blank=True, null=True)

    title = models.CharField(max_length=150)
    seats_per_row = models.IntegerField(default=10)

    category = models.ForeignKey(
        EventCategory,
        on_delete=models.CASCADE,
        related_name='events',
        null=True,
        blank=True
    )

    campus = models.ForeignKey(Campus, on_delete=models.CASCADE)

    location = models.CharField(max_length=150)

    event_datetime = models.DateTimeField()
    end_time = models.TimeField(blank=True, null=True)

    description = models.TextField(blank=True, null=True)

    total_capacity = models.PositiveIntegerField()

    price = models.DecimalField(max_digits=8, decimal_places=2)

    discount_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )

    discount_end = models.DateTimeField(null=True, blank=True)

    rows = models.IntegerField(default=10)
    columns = models.IntegerField(default=10)

    vip_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )

    class Meta:
        ordering = ['event_datetime']

    def clean(self):

    

        # ==========================================
        # 1. BASIC VALIDATION
        # ==========================================
        if self.end_time and self.event_datetime:
            if self.end_time <= self.event_datetime.time():
                raise ValidationError({
                    "end_time": "End time must be after start time."
                })

        # ==========================================
        # 2. CONFLICT CHECK
        # ==========================================
        conflicts = Event.objects.filter(
            campus=self.campus,
            location=self.location,
            event_datetime__date=self.event_datetime.date()
        ).exclude(pk=self.pk)

        new_start = self.event_datetime

        new_end = None
        if self.end_time:
            new_end = make_aware(
                datetime.combine(self.event_datetime.date(), self.end_time)
            )

        for e in conflicts:

            old_start = e.event_datetime

            old_end = None
            if e.end_time:
                old_end = make_aware(
                    datetime.combine(e.event_datetime.date(), e.end_time)
                )

            # ==========================================
            # SKIP EVENTS THAT ARE ALREADY FINISHED
            # ==========================================
            if old_end and old_end <= timezone.now():
                continue

            # ==========================================
            # OVERLAP CHECK (MAIN LOGIC)
            # ==========================================
            if new_end and old_end:
                if old_start < new_end and old_end > new_start:
                    raise ValidationError(
                        "❌ Conflict: Another event overlaps with this time at the same location."
                    )

            # ==========================================
            # FALLBACK (if no end times exist)
            # ==========================================
            else:
                if old_start.date() == new_start.date():
                    raise ValidationError(
                        "❌ Conflict: Another event already exists on this date in this location."
                    )
                
    def __str__(self):
        return f"{self.title} - {self.campus.name}"


# ==========================================
# SEAT MODEL
# ==========================================

class Seat(models.Model):

    TICKET_TYPES = [
        ("Standard", "Standard"),
        ("VIP", "VIP"),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="seats"
    )

    seat_number = models.CharField(max_length=5)

    ticket_type = models.CharField(
        max_length=10,
        choices=TICKET_TYPES,
        default="Standard"
    )

    def __str__(self):
        return f"{self.event.title} - {self.seat_number}"

    def is_booked(self):
        return hasattr(self, "ticket")


# ==========================================
# TICKET MODEL
# ==========================================

class Ticket(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='tickets'
    )

    seat = models.OneToOneField(
        Seat,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    ticket_type = models.CharField(max_length=10)

    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    purchased_at = models.DateTimeField(default=timezone.now)

    ticket_number = models.CharField(
        max_length=12,
        unique=True,
        blank=True
    )

    def save(self, *args, **kwargs):

        if not self.ticket_number:
            self.ticket_number = str(uuid.uuid4())[:12]

        if self.seat:

            self.ticket_type = self.seat.ticket_type

            if self.seat.ticket_type == "VIP":
                self.price = self.event.vip_price
            else:

                if (
                    self.event.discount_price
                    and self.event.discount_end
                    and timezone.now() <= self.event.discount_end
                ):
                    self.price = self.event.discount_price
                else:
                    self.price = self.event.price

        super().save(*args, **kwargs)

        
      
    def __str__(self):
        return f"{self.event.title} - {self.ticket_number}"



# ==========================================
# PAYMENT MODEL
# ==========================================

class Payment(models.Model):

    PAYMENT_METHODS = [
        ('visa', 'Visa'),
        ('mastercard', 'MasterCard'),
        ('paypal', 'PayPal'),
    ]

    PAYMENT_STATUS = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    event = models.ForeignKey(Event, on_delete=models.CASCADE)

    amount = models.DecimalField(max_digits=8, decimal_places=2)

    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)

    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS,
        default='Pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.event.title}"
    

class PriceHistory(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="price_history")
    old_price = models.DecimalField(max_digits=10, decimal_places=2)
    new_price = models.DecimalField(max_digits=10, decimal_places=2)
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event.title}: {self.old_price} → {self.new_price}"