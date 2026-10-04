from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'tickets'

urlpatterns = [
    # Home page
    path('', views.home, name='home'),

    # Login / Logout
    path('login/', views.student_login, name='login'),
    path('logout/', views.student_logout, name='logout'),

    # Tickets & Events
    path('my-tickets/', views.my_tickets, name='my_tickets'),
    path('events/', views.events, name='events'),
    path('events/<int:event_id>/', views.event_detail, name='event_detail'),
    path('choose-seat/<int:event_id>/', views.choose_seat, name='choose_seat'),
    path('book-event/<int:event_id>/', views.book_event, name='book_event'),
    path('ticket/<int:pk>/', views.ticket_detail, name='ticket_detail'),

    # Profile & Dashboard
    path('profile/', views.profile, name='profile'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),

    # Contact
    path('contact/', views.contact, name='contact'),

    # Reservation success (includes payment info)
    path('events/<int:event_id>/success/', views.reservation_success, name='reservation_success'),

    # Admin / setup (create seats for event)
    path('create-seats/<int:event_id>/', views.create_seats_for_event, name='create_seats'),
     path(
        'admin/tickets/event/generate-seats/<int:event_id>/',
        views.create_seats_for_event,
        name='generate-seats'
    ),
    path(
    'admin/tickets/event/event-report/<int:event_id>/',
    views.event_report_view,
    name='event_report'
),
    
]

# Media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)