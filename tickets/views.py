# Django shortcuts
from django.shortcuts import render, redirect, get_object_or_404

# Authentication
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required

# Messages framework
from django.contrib import messages

# Database & ORM
from django.db import transaction
from django.db.models import Count, Sum, F, Q, Exists, OuterRef, IntegerField
from django.db.models.functions import Substr, Cast

# Utilities
from django.utils import timezone
from django.utils.dateparse import parse_date

# Templates
from django.template.response import TemplateResponse

# Email
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings

# Local app imports
from .models import Event, Ticket
from .forms import UserProfileForm
from .models import (
    Event,
    EventCategory,
    Ticket,
    Payment,
    
    Seat,
)

#Import Q object for advanced queries (used in filtering logic )
from django.db.models import Q

from .payment_observer import PaymentProcessor, TicketGenerator
from datetime import datetime

import string

# Get the currently active User model (supports custom user models)
User = get_user_model()

# ==========================================================
# HOME PAGE
# ==========================================================
def home(request):

    # Fetch upcoming events and identify "trending" ones
    # Trending = events with low remaining tickets (< 30)
    trending_events = (
        Event.objects.filter(event_datetime__gte=timezone.now())
        .annotate(tickets_booked=Count("tickets"))
        .annotate(tickets_left=F("total_capacity") - F("tickets_booked"))
        .filter(tickets_left__lt=30)
    )

    # Fetch events with active discounts (limited offers)

    limited_events = (
        Event.objects.filter(
            discount_price__isnull=False,  # Event has a discount
            discount_end__gte=timezone.now()  # Discount is still valid
        )
        .annotate(tickets_booked=Count("tickets"))
        .annotate(tickets_left=F("total_capacity") - F("tickets_booked"))
        .order_by('discount_end')[:6]  # Show only top 6 ending soon
    )

     # If user is logged in, check if they already booked each event

    if request.user.is_authenticated:
        trending_events = trending_events.annotate(
            is_booked=Exists(
                Ticket.objects.filter(user=request.user, event=OuterRef("pk"))
            )
        )

        limited_events = limited_events.annotate(
            is_booked=Exists(
                Ticket.objects.filter(user=request.user, event=OuterRef("pk"))
            )
        )
    else:
         # If user is not logged in, default is_booked to False (0)
        trending_events = trending_events.annotate(is_booked=F("id") * 0)
        limited_events = limited_events.annotate(is_booked=F("id") * 0)


# Render homepage with event data
    return render(request, "tickets/home.html", {
        "trending_events": trending_events,
        "limited_events": limited_events,
        "now": timezone.now(),
    })

# ==========================================================
# EVENT CONFLICT CHECK
# ==========================================================

def has_conflict(user, new_event):

    """
    Checks if the user already has a booking that overlaps
    with the new event timing.
    Prevents users from booking two events at the same time.
    """

    # Start time of new event

    new_start = new_event.event_datetime

     # Calculate end time of new event 
    new_end = new_event.event_datetime.replace(
        hour=new_event.end_time.hour,
        minute=new_event.end_time.minute
    ) if new_event.end_time else None

 # Get all tickets booked by the user
    user_tickets = Ticket.objects.filter(user=user).select_related("event")

 # Loop through each booked event
    for t in user_tickets:
        e = t.event

        # 1. ROOM CONFLICT CHECK 
        if e.location == new_event.location:
            return True

        old_start = e.event_datetime

         # Calculate end time of existing event
        old_end = e.event_datetime.replace(
            hour=e.end_time.hour,
            minute=e.end_time.minute
        ) if e.end_time else None

        # If no end time, only compare dates

        if not old_end or not new_end:
            if old_start.date() == new_start.date():
                return True

# Check time overlap condition
        if old_start < new_end and old_end > new_start:
            return True  # Conflict exists

    return False  # No conflict



# ==========================================================
# LOGIN / LOGOUT
# ==========================================================
def student_login(request):

     # Handle login form submission
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

# Authenticate user credentials
        user = authenticate(request, username=username, password=password)

        if user:
            # Login successful
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect("tickets:home")
        else:
            # Invalid credentials : show error
            return render(request, "tickets/login.html", {
                "username": username,
                "error": "Incorrect email or password"
            })
        # If GET request then just show login page
    return render(request, "tickets/login.html")


def student_logout(request):
    # Log out the current user
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("tickets:home")

# ==========================================================
# MY TICKETS
# ==========================================================


@login_required  # Only logged-in users can access
def my_tickets(request):
    # Retrieve all tickets belonging to the current user
    tickets = Ticket.objects.filter(user=request.user)
    # Debug print
    print("DEBUG TICKETS:", tickets)
    return render(request, "tickets/my_tickets.html", {"tickets": tickets})

# ==========================================================
# PROFILE
# ==========================================================
@login_required
def profile(request):
    # Display user profile page
    return render(request, "tickets/profile.html")

# ==========================================================
# EVENTS PAGE (Search + Category)
# ==========================================================
def events(request):
    # Get search query, selected category, and selected date from URL parameters
    q = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "")
    selected_date = request.GET.get("day", "")  # get the day input

    # Retrieve all event categories
    categories = EventCategory.objects.all()

 # Loop through each category to group events
    for category in categories:

        # Base queryset: upcoming events for this category
        events_qs = Event.objects.filter(
            category=category,
            event_datetime__gte=timezone.now()
        )

 # Apply search filter (title or location)
        if q:
            events_qs = events_qs.filter(
                Q(title__icontains=q) | Q(location__icontains=q)
            )

 # Apply category filter (if user selected one)

        if selected_category:
            events_qs = events_qs.filter(category__id=selected_category)

 # Annotate ticket data (number booked and remaining seats)

        events_qs = events_qs.annotate(
            tickets_booked=Count("tickets"),
            tickets_left=F("total_capacity") - Count("tickets"),
        )

# Apply date filter (if user selected a specific day)
        if selected_date:
            # Convert to date object
            date_obj = parse_date(selected_date) 
            if date_obj:
                events_qs = events_qs.filter(
                    event_datetime__date=date_obj
                )

 # Re-annotate to ensure ticket data is updated after filtering
        events_qs = events_qs.annotate(
        tickets_booked=Count("tickets"),
        tickets_left=F("total_capacity") - Count("tickets"),)

 # If user is logged in, check if they already booked each event
        if request.user.is_authenticated:
            events_qs = events_qs.annotate(
                is_booked=Exists(
                    Ticket.objects.filter(user=request.user, event=OuterRef("pk"))
                )
            )
        else:
             # Default value for non-authenticated users
            events_qs = events_qs.annotate(is_booked=F("id") * 0)

# Attach filtered and annotated events to the category
        category.annotated_events = events_qs

# Render events page with filters and categorized results

    return render(request, "tickets/events.html", {
        "categories": categories,
        "q": q,
        "selected_category": selected_category,
        "selected_date": selected_date, 
    })

# ==========================================================
# EVENT DETAIL
# ==========================================================
def event_detail(request, event_id):

    # Retrieve event or return 404 if not found
    event = get_object_or_404(Event, id=event_id)

     # Annotate event with ticket statistics
    event = (
        Event.objects.filter(id=event_id)
        .annotate(tickets_booked=Count("tickets"))
        .annotate(tickets_left=F("total_capacity") - F("tickets_booked"))
        .first()
    )

# Determine current price based on discount validity
    if event.discount_price and event.discount_end and timezone.now() <= event.discount_end:
        event.current_price = event.discount_price
    else:
        event.current_price = event.price

        # Render event detail page
    return render(request, "tickets/event_detail.html", {"event": event})

# ==========================================================
# CARD VALIDATION (LUHN)
# ==========================================================
def validate_card(card_number):
    # Check if input is empty
    if not card_number:
        return False
    
     # Remove spaces from input (e.g. "1234 5678" to "12345678")
    card_number = card_number.replace(" ", "")

    # Ensure all characters are digits
    if not card_number.isdigit():
        return False
    total = 0

    # Reverse the card number for Luhn processing
    reverse_digits = card_number[::-1]

    # Loop through each digit with its index
    for i, digit in enumerate(reverse_digits):
        n = int(digit)

         # Double every second digit (Luhn rule)
        if i % 2 == 1:
            n *= 2

             # If result > 9, subtract 9
            if n > 9:
                n -= 9
        total += n

         # Valid card if total is divisible by 10
    return total % 10 == 0

# ==========================================================
# DETECT CARD TYPE
# ==========================================================
def detect_card_type(card_number):

    # Remove spaces for consistent checking
    card_number = card_number.replace(" ", "")

     # Visa cards start with 4
    if card_number.startswith("4"):
        return "visa"
    
    # Mastercard ranges:
    # 51–55 OR 2221–2720
    if (len(card_number) >= 2 and 51 <= int(card_number[:2]) <= 55) or \
       (len(card_number) >= 4 and 2221 <= int(card_number[:4]) <= 2720):
        return "mastercard"
    
    # Unknown card type
    return "unknown"

# ==========================================================
# CHOOSE SEAT
# ==========================================================

@login_required  # Only logged-in users can access seat selection
def choose_seat(request, event_id):
    # Retrieve event or return 404 if not found
    event = get_object_or_404(Event, id=event_id)

    
    # Retrieve all seats for the event
    # Annotate to extract:
    # - row_letter (A, B, C...)
    # - seat number as integer (for proper ordering)
    seats = Seat.objects.filter(event=event).annotate(
    row_letter=Substr("seat_number", 1, 1),
    seat_num=Cast(Substr("seat_number", 2), IntegerField())
).order_by("row_letter", "seat_num")

    # Get IDs of already booked seats
    booked_seats = list(
        Ticket.objects.filter(event=event).values_list("seat_id", flat=True)
    )

    # Group seats by row letter (A, B, C, etc.)
    seat_rows = {}

    for seat in seats:
        row_letter = seat.row_letter  # first letter of seat (A1 = A)

 # Initialize list if row doesn't exist
        if row_letter not in seat_rows:
            seat_rows[row_letter] = []

# Add seat to corresponding row
        seat_rows[row_letter].append(seat)

    # After grouping seats by row
    # Assign dynamic pricing for each seat
    for seat in seats:
        if seat.ticket_type == "VIP":
            # VIP seats have fixed VIP price
            seat.current_price = event.vip_price
        else:
            # Apply discount if valid and available
            if event.discount_price and event.discount_end and timezone.now() <= event.discount_end:
                seat.current_price = event.discount_price
            else:
                # Default standard price
                seat.current_price = event.price

    
 # Handle seat selection form submission
    if request.method == "POST":
        seat_id = request.POST.get("seat_id")

        if seat_id:
             # Store selected seat in session for booking step
            request.session["selected_seat"] = seat_id

             # Redirect to booking page
            return redirect("tickets:book_event", event_id=event.id)
        else:
            # Error if no seat selected
            messages.error(request, "Please select a seat.")

# Render seat selection page
    return render(request, "tickets/choose_seat.html", {
        "event": event,
        "seat_rows": seat_rows,  # Organized seats by rows
        "booked_seats": booked_seats,  # Used to disable unavailable seats
    })

    

# ==========================================================
# BOOK EVENT (Observer Pattern)
# ==========================================================

@login_required  # Ensure only authenticated users can book tickets
def book_event(request, event_id):

    # Retrieve event or return 404 if not found
    event = get_object_or_404(Event, id=event_id)

    # Retrieve selected seat from session
    seat_id = request.session.get("selected_seat")

    # If no seat selected, redirect back
    if not seat_id:
        messages.error(request, "No seat selected!")
        return redirect("tickets:choose_seat", event_id=event.id)
    
      # Get the seat linked to the event

    seat = get_object_or_404(Seat, id=seat_id, event=event)
    conflicting_event = None

 # Check if user already has an event at the same time
    if has_conflict(request.user, event):
        for t in Ticket.objects.filter(user=request.user).select_related("event"):
            if t.event.event_datetime.date() == event.event_datetime.date():
                conflicting_event = t.event
                break
    # Warn user if conflict exists
    if has_conflict(request.user, event):
        messages.warning(
            request,
            "Warning : You already have another event that overlaps with this time!"
        )

    # =========================
    # Compute ticket price for GET and POST
    # =========================
    if seat.ticket_type == "VIP":
        ticket_price = event.vip_price
    else:
        # Apply discount if valid
        if event.discount_price and event.discount_end and timezone.now() <= event.discount_end:
            ticket_price = event.discount_price
        else:
            ticket_price = event.price

    # =========================
    # Handle POST (booking)
    # =========================

    if request.method == "POST":
        # Get payment details
        payment_method = request.POST.get("payment_method")
        card_number = request.POST.get("card_number", "").strip()
        card_type = None
        

        # ===== CARD PAYMENT =====
        if payment_method == "card":
            # Validate card using Luhn algorithm
            if not validate_card(card_number):
                messages.error(request, "Invalid card number.")
                return redirect("tickets:book_event", event_id=event.id)

# Detect card type (Visa / Mastercard)
            card_type = detect_card_type(card_number).lower()
            if card_type == "unknown":
                messages.error(request, "Only Visa or Mastercard supported.")
                return redirect("tickets:book_event", event_id=event.id)

# Use detected card type as payment method
            payment_method = card_type

        # ===== PAYPAL =====
        elif payment_method == "paypal":
            card_type = "paypal"
            # Invalid payment method
        else:
            messages.error(request, "Invalid payment method.")
            return redirect("tickets:book_event", event_id=event.id)

        try:

            # =========================
            # DATABASE TRANSACTION
            # =========================
            with transaction.atomic():
                # Lock the seat row to prevent double booking
                seat = Seat.objects.select_for_update().get(id=seat_id, event=event)
                # Check if seat already booked
                if Ticket.objects.filter(seat=seat).exists():
                    messages.error(request, "Seat already booked.")
                    return redirect("tickets:choose_seat", event_id=event.id)

                # Create ticket
                ticket = Ticket.objects.create(
                    user=request.user,
                    event=event,
                    seat=seat,
                    price=ticket_price
                )

                # Create payment record
                payment = Payment.objects.create(
                    user=request.user,
                    event=event,
                    amount=ticket.price,
                    method=payment_method,
                    status="Pending"
                )

                # =========================
                # OBSERVER PATTERN
                # =========================
                # Process payment using observer pattern
                # Create payment processor (subject)
                processor = PaymentProcessor()
                # Attach observer (ticket generator)
                processor.attach(TicketGenerator())
                 # Process payment then notifies observers automatically
                if payment_method == "paypal":
                    # simulate instant success
                    payment.status = "Paid"
                    payment.save()

                    success = True

                else:
                    success = processor.process_payment(payment)
                                                
# If payment fails : rollback logic
                if not success:
                    ticket.delete()
                    messages.error(request, "Payment failed.")
                    return redirect("tickets:book_event", event_id=event.id)

                
               
                        
                # =========================
                # EMAIL ONLY AFTER SUCCESS
                # =========================
                subject = "🎟️ Ticket Confirmation"

                # HTML email content

                html_content = f"""
                <html>
                <body style="font-family: Arial; background:#f5efe6; padding:20px;">
                    
                    <div style="max-width:600px; margin:auto; background:white; padding:20px; border-radius:12px;">
                    
                    <h2 style="color:#1f2a38;">🎉🥳 Booking Confirmed!</h2>

                    <p>Hi <b>{request.user.username}</b>,</p>

                    <p>Your ticket has been successfully booked.</p>

                    <hr>

                    <h3>🎟️ Event Details</h3>
                    <p><b>Event:</b> {event.title}</p>
                    <p><b>Seat:</b> {seat.seat_number}</p>
                    <p><b>Price:</b> Rs {ticket.price}</p>

                    <hr>

                    <p style="color:green;"><b>✔ Payment Successful</b></p>

                    <p style="margin-top:20px;">Thank you for booking with us 😎</p>

                    </div>

                </body>
                </html>
                """
 # Create email
                email = EmailMultiAlternatives(
                    subject,
                    "Your ticket is confirmed.",
                    settings.DEFAULT_FROM_EMAIL,
                    [request.user.email]
                )
# Attach HTML version
                email.attach_alternative(html_content, "text/html")
                email.send()  # Send email
                                                    


                # Handle unexpected errors

        except Exception as e:
            print("BOOK EVENT ERROR:", e)
            messages.error(request, f"Error: {e}")
            return redirect("tickets:book_event", event_id=event.id)

        # Clear selected seat from session
        request.session.pop("selected_seat", None)

         # Redirect to success page
        return redirect("tickets:reservation_success", event_id=event.id)

    # =========================
    # Render GET page
    # =========================
    # Display booking page with:
# - Event details
# - Selected seat
# - Calculated ticket price
# - Any conflicting event warning
    return render(request, "tickets/book_event.html", {
        "event": event,
        "selected_seat": seat,
        "ticket_price": ticket_price,
        "conflicting_event": conflicting_event,
    })

# ==========================================================
# DASHBOARD(Profile Management)
# ==========================================================
@login_required

def dashboard(request):
    user = request.user

    # Handle profile update (POST)

    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile picture updated!")
            return redirect("tickets:dashboard")
        
        # Display existing profile (GET)
    else:
        form = UserProfileForm(instance=user)

    return render(request, "tickets/edit_profile.html", {
        "user": user,
        "form": form
    })

# ==========================================================
# EDIT PROFILE (separate profile edit page)
# ==========================================================

@login_required
def edit_profile(request):

    if request.method == "POST":
        form = UserProfileForm(
            request.POST,
            request.FILES,
            instance=request.user
        )
# Save updated user details
        if form.is_valid():
            form.save()
            return redirect("tickets:dashboard")

    else:
        form = UserProfileForm(instance=request.user)

    return render(request, "tickets/edit_profile.html", {"form": form})

# ==========================================================
# RESERVATION SUCCESS
# ==========================================================
@login_required
def reservation_success(request, event_id):
    # Get event details
    event = get_object_or_404(Event, id=event_id)

     # Retrieve user's tickets for this event (latest first)
    tickets = Ticket.objects.filter(user=request.user, event=event).order_by("-purchased_at")
    
    # Retrieve latest payment
    payment = Payment.objects.filter(user=request.user, event=event).order_by("-created_at").first()

    return render(request, "tickets/payment_success.html", {
        "event": event,
        "tickets": tickets,
        "card_type": payment.method if payment else None
    })

# ==========================================================
#  STATIC PAGE (CONTACT)
# ==========================================================
def contact(request):
    return render(request, "tickets/contact.html")


# ==========================================================
# TICKET DETAIL VIEW
# ==========================================================

@login_required
def ticket_detail(request, pk):
    # Ensure user can only view their own ticket
    ticket = get_object_or_404(Ticket, pk=pk, user=request.user)
    return render(request, "tickets/ticket_detail.html", {"ticket": ticket})


# ==========================================================
# SEAT GENERATION (Matrix-like layout)
# ==========================================================

def create_seats_for_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # SAFETY: delete old seats
    Seat.objects.filter(event=event).delete()

    total_seats = event.total_capacity
    seats_per_row = event.seats_per_row

    alphabet = string.ascii_uppercase
    seat_count = 0

    for row_index, row_letter in enumerate(alphabet):

        for num in range(1, seats_per_row + 1):

            if seat_count >= total_seats:
                break

            ticket_type = "VIP" if row_index < 2 else "Standard"

            Seat.objects.create(
                event=event,
                seat_number=f"{row_letter}{num}",
                ticket_type=ticket_type,
            )

            seat_count += 1

        if seat_count >= total_seats:
            break

    messages.success(request, "Seats generated correctly.")
    return redirect("tickets:choose_seat", event_id=event.id)

# ==========================================================
# EVENT REPORT (ADMIN ANALYTICS)
# ==========================================================

def event_report_view(self, request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # Fetch all tickets with related user and seat info
    tickets = event.tickets.select_related("user", "seat")

# Categorize tickets
    vip_tickets = tickets.filter(seat__ticket_type="VIP")
    standard_tickets = tickets.filter(seat__ticket_type="Standard")

    # =========================
    # STATISTICS
    # =========================

    # Counts
    # Total tickets sold
    total_tickets_sold = tickets.count()

    # Ticket counts by type
    vip_count = vip_tickets.count()
    standard_count = standard_tickets.count()

    # Revenue calculations
    total_revenue = tickets.aggregate(total=Sum("price"))["total"] or 0
    vip_revenue = vip_tickets.aggregate(total=Sum("price"))["total"] or 0
    standard_revenue = standard_tickets.aggregate(total=Sum("price"))["total"] or 0

    
    # =========================
    # TOP BUYERS ANALYSIS
    # =========================
    top_buyers = Ticket.objects.values(
        'user__first_name',
        'user__last_name'
    ).annotate(
        tickets_count=Count('id'),
        total_spent=Sum('price')
    ).order_by('-tickets_count')
        
    # =========================
    # GROUP TICKETS BY PRICE
    # =========================
    # Group by price
    price_groups = {}
    for ticket in tickets:
        price_groups.setdefault(ticket.price, []).append(ticket)

        # Context passed to admin report template

    context = {
        "event": event,
        "tickets": tickets,
        "vip_tickets": vip_tickets,
        "standard_tickets": standard_tickets,
        "price_groups": price_groups,

       
        "total_tickets_sold": total_tickets_sold,
        "vip_count": vip_count,
        "standard_count": standard_count,

        "total_revenue": total_revenue,
        "vip_revenue": vip_revenue,
        "standard_revenue": standard_revenue,

        "top_buyers": top_buyers,
        "now": timezone.now(),
    }

    return TemplateResponse(request, "admin/event_report.html", context)



# ==========================================================
# CARD EXPIRY VALIDATION
# ==========================================================

def validate_expiry(expiry):
    try:
         # Split MM/YY format
        month, year = expiry.split("/")
        month = int(month)
        year = int(year)

# Validate month range
        if month < 1 or month > 12:
            return False

# Get current date
        now = datetime.now()
        current_year = now.year % 100
        current_month = now.month

# Check if card is expired
        if year < current_year or (year == current_year and month < current_month):
            return False

        return True
    except:
        return False


# ==========================================================
# CVV VALIDATION
# ==========================================================
def validate_cvv(cvv):
    # Must be numeric and length 3 or 4
    return cvv.isdigit() and len(cvv) in [3, 4]