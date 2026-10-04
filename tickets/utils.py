from django.template.loader import render_to_string
from django.http import HttpResponse
from xhtml2pdf import pisa
from io import BytesIO
from django.db.models import Sum
from django.conf import settings
import os

def generate_event_pdf(event):

    tickets = event.tickets.all()

    total_revenue = tickets.aggregate(total=Sum("price"))["total"] or 0

    vip_count = tickets.filter(ticket_type="VIP").count()
    standard_count = tickets.filter(ticket_type="Standard").count()

    tickets_sold = tickets.count()

    seats_left = event.total_capacity - tickets_sold

    event_image = event.image.url if event.image else None

    html = render_to_string(
        "admin/event_report.html",
        {
            "event": event,
            "tickets": tickets,
            "total_revenue": total_revenue,
            "vip_count": vip_count,
            "standard_count": standard_count,
            "tickets_sold": tickets_sold,
            "seats_left": seats_left,
            "event_image": event_image,
        }
    )

    result = BytesIO()

    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)

    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type="application/pdf")

    return HttpResponse("Error generating PDF", status=500)


