# ==========================================
# IMPORTS
# ==========================================

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.html import format_html
from django.db.models import Sum, Count
from django.urls import path
from django.template.response import TemplateResponse
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone


from .models import PriceHistory
import json
import string


from .models import (
    User,
    Campus,
    Event,
    Ticket,
    EventCategory,
    Payment,
    Seat,
)

from .utils import generate_event_pdf


# ==========================================
# CUSTOM USER FORMS
# ==========================================

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "university_id", "role")


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = (
            "username",
            "email",
            "university_id",
            "role",
            "is_active",
            "is_staff",
            "is_superuser",
        )


# ==========================================
# USER ADMIN
# ==========================================

@admin.register(User)
class UserAdmin(DjangoUserAdmin):

    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User

    list_display = (
        "username",
        "first_name",
        "last_name",
        "email",
        "university_id",
        "role",
        "is_staff",
        "is_active",
    )

    list_filter = ("role", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "university_id")
    ordering = ("username",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "email", "university_id", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username","first_name",
            "last_name", "email", "university_id", "role", "password1", "password2"),
        }),
    )


# ==========================================
# CAMPUS ADMIN
# ==========================================

@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


# ==========================================
# EVENT CATEGORY ADMIN
# ==========================================

@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


# ==========================================
# EVENT ADMIN
# ==========================================

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):


    list_display = (
        "title",
        "campus",
        "location",
        "event_datetime",
        "total_capacity",
        "tickets_sold_display",
        "tickets_left_display",
        "total_revenue_display",
        "report_button",
        "image_preview",
    )

    list_filter = ("campus", "event_datetime")
    search_fields = ("title", "location")

    fields = (
        "title",
        "campus",
        "location",
        "category",
        "event_datetime",
        "end_time",
        "description",
        "price",
        "discount_price",
        "discount_end",
        "vip_price",
        "total_capacity",
        "seats_per_row",
        "image",
    )

    # ==========================================
    # SAFE SAVE MODEL
    # ==========================================

    def save_model(self, request, obj, form, change):

        # Track price changes (only if updating)
        if change:
            old_obj = Event.objects.get(pk=obj.pk)

            if old_obj.price != obj.price:
                PriceHistory.objects.create(event=obj, old_price=old_obj.price, new_price=obj.price)

            if old_obj.vip_price != obj.vip_price:
                PriceHistory.objects.create(event=obj, old_price=old_obj.vip_price, new_price=obj.vip_price)

        # SAVE FIRST (IMPORTANT)
        super().save_model(request, obj, form, change)

        # ==========================================
        # CASE 1: NEW EVENT → GENERATE SEATS
        # ==========================================
        if not change:
            self._generate_seats(obj)
            messages.success(request, "Seats generated successfully.")
            return

        # ==========================================
        # CASE 2: UPDATE EVENT → REGENERATE IF NEEDED
        # ==========================================
        regenerate_seats = (
            old_obj.total_capacity != obj.total_capacity
            or old_obj.seats_per_row != obj.seats_per_row
        )

        if regenerate_seats:
            if obj.tickets.exists():
                messages.error(request, "Cannot regenerate seats because tickets already exist.")
                return

            Seat.objects.filter(event=obj).delete()
            self._generate_seats(obj)
            messages.success(request, "Seats regenerated successfully.")

    # ==========================================
    # HELPER: SEAT GENERATION
    # ==========================================
    
    def _generate_seats(self, event):
        import string

        alphabet = string.ascii_uppercase
        total_seats = event.total_capacity
        seats_per_row = event.seats_per_row

        seat_count = 0

        for row_index, row_letter in enumerate(alphabet):
            for num in range(1, seats_per_row + 1):

                if seat_count >= total_seats:
                    return

                ticket_type = "VIP" if row_index < 2 else "Standard"

                Seat.objects.create(
                    event=event,
                    seat_number=f"{row_letter}{num}",
                    ticket_type=ticket_type,
                )

                seat_count += 1
                    

        

    # ==========================================
    # DISPLAY METHODS
    # ==========================================

    def tickets_sold_display(self, obj):
        return obj.tickets.count()
    tickets_sold_display.short_description = "Tickets Sold"

    def tickets_left_display(self, obj):
        return obj.total_capacity - obj.tickets.count()
    tickets_left_display.short_description = "Tickets Left"

    def total_revenue_display(self, obj):
        from django.db.models import Sum
        total = obj.tickets.aggregate(total=Sum("price"))["total"]
        return total or 0
    total_revenue_display.short_description = "Revenue"

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="60"/>', obj.image.url)
        return "-"
    image_preview.short_description = "Image"
    # ==========================================
    # CUSTOM ADMIN URLS
    # ==========================================

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "generate-pdf/<int:event_id>/",
                self.admin_site.admin_view(self.pdf_view),
                name="generate-pdf",
            ),
            path(
                "sales-graph/<int:event_id>/",
                self.admin_site.admin_view(self.sales_graph_view),
                name="sales-graph",
            ),
            path(
                "generate-seats/<int:event_id>/",
                self.admin_site.admin_view(self.generate_seats_view),
                name="generate-seats",
            ),

                path(
        "event-report/<int:event_id>/",
        self.admin_site.admin_view(self.event_report_view),
        name="event-report",
    ),

        
        ]

        return custom_urls + urls

    # ==========================================
    # PDF
    # ==========================================

    def pdf_view(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)
        return generate_event_pdf(event)

    
   # ==========================================
    # EVENT REPORT
    # ==========================================

    def event_report_view(self, request, event_id):
        
        event = get_object_or_404(Event, id=event_id)
        tickets = event.tickets.select_related("user", "seat")

        vip_tickets = tickets.filter(seat__ticket_type="VIP")
        standard_tickets = tickets.filter(seat__ticket_type="Standard")

        # Counts
        total_tickets_sold = tickets.count()
        vip_count = vip_tickets.count()
        standard_count = standard_tickets.count()

        # Revenue
        total_revenue = tickets.aggregate(total=Sum("price"))["total"] or 0
        vip_revenue = vip_tickets.aggregate(total=Sum("price"))["total"] or 0
        standard_revenue = standard_tickets.aggregate(total=Sum("price"))["total"] or 0

        # Top buyers
        top_buyers = (
            tickets.values("user__username")
            .annotate(
                total_spent=Sum("price"),
                tickets_count=Count("id")
            )
            .order_by("-total_spent")[:5]
        )

        # Group by price
        price_groups = {}
        for ticket in tickets:
            price_groups.setdefault(ticket.price, []).append(ticket)

        # Initial seats
        initial_seats = event.total_capacity

        # Profit calculation
        profit = vip_revenue - standard_revenue

        # Available seats
        available_seats = initial_seats - total_tickets_sold

        context = {
            "event": event,
            "initial_seats": initial_seats,
            "available_seats": available_seats, 
            "event_description": event.description,
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
            "profit": profit,  

            "top_buyers": top_buyers,
            "now": timezone.now(),
        }

        return TemplateResponse(request, "admin/event_report.html", context)
    def report_button(self, obj):
        return format_html(
            '<a class="button" href="event-report/{}/">Generate Report</a>',
            obj.id
        )

    report_button.short_description = "Report"

    # ==========================================
    # SALES GRAPH
    # ==========================================

    def sales_graph_view(self, request, event_id):

        event = get_object_or_404(Event, id=event_id)
        tickets = event.tickets.all()

        sales_data = {}

        for ticket in tickets:
            day = ticket.purchased_at.date().isoformat()
            sales_data[day] = sales_data.get(day, 0) + 1

        return TemplateResponse(
            request,
            "admin/sales_graph.html",
            {
                "event": event,
                "sales_data": json.dumps(sales_data),
            },
        )

    # ==========================================
    # GENERATE SEATS BUTTON
    # ==========================================
    def generate_seats_view(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)
        if event.tickets.exists():
            messages.error(request, "Cannot regenerate seats because tickets already exist.")
            return redirect(f"/admin/your_app/event/{event.id}/change/")

        self._generate_seats(event)
        messages.success(request, f"{event.total_capacity} seats generated successfully.")
        return redirect(f"/admin/your_app/event/{event.id}/change/")

# ==========================================
# TICKET ADMIN
# ==========================================

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):

    list_display = (
        "seat_number",
        "user",
        "event",
        "price",
        "purchased_at",
    )

    list_filter = ("event", "purchased_at")
    search_fields = ("seat__seat_number", "user__username", "event__title")
    ordering = ("-purchased_at",)

    def seat_number(self, obj):
        return obj.seat.seat_number if obj.seat else "No Seat"

    seat_number.short_description = "Seat"


# ==========================================
# PAYMENT ADMIN
# ==========================================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "event",
        "amount",
        "method",
        "status",
        "created_at",
    )

    list_filter = ("method", "status", "created_at")
    search_fields = ("user__username", "event__title")
    ordering = ("-created_at",)



