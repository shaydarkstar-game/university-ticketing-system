# 🎟️ University Event Ticketing System

A Django-based web application designed to simplify university event management and online ticket booking.

The system allows students to discover university events, select seats, make simulated payments, and manage their tickets, while staff and administrators can manage events, monitor bookings, and generate sales reports.

---

## 📌 Project Overview

The University Event Ticketing System was developed as a Software Engineering project to provide a centralized platform for managing university events and ticket reservations.

The application focuses on applying software engineering principles such as Object-Oriented Programming, database management, authentication, role-based access control, design patterns, transaction handling, and automated ticket generation.

---

## ✨ Key Features

### 👤 User Management
- Student, staff, and administrator roles
- User registration and authentication
- University ID and email validation
- Profile management
- Profile picture support

### 🎫 Event Management
- Browse available university events
- Event categories
- Event images
- Event dates, times, and locations
- Event capacity management
- VIP and standard ticket options
- Discount pricing
- Event availability tracking

### 💺 Seat Selection
- Interactive seat selection
- Seat availability management
- Different ticket types
- Prevention of duplicate seat bookings

### 💳 Payment Processing
- Simulated Visa, Mastercard, and PayPal payment options
- Card validation using the Luhn algorithm
- Payment status tracking
- Payment confirmation

> **Note:** Payment processing is simulated for academic purposes and does not process real financial transactions.

### 🎟️ Ticket Generation
- Automatic ticket generation after successful payment
- Ticket information linked to the selected event and seat
- Users can view their booked tickets

### 📊 Administrative Reporting
- Event sales reports
- Booking information
- Sales data visualization
- Administrative event management

### 📧 Email Notifications
- Email-based notifications
- Payment and booking-related communication

---

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| Python | Application programming |
| Django | Web application framework |
| PostgreSQL | Relational database |
| HTML5 | Page structure |
| CSS3 | Styling |
| JavaScript | Client-side functionality |
| Bootstrap | Responsive UI components |
| SMTP / Gmail | Email notifications |
| Git & GitHub | Version control |

---

## 🏗️ Project Structure

```text
university-ticketing-system/
│
├── media/
│   ├── event_images/
│   └── profile_pics/
│
├── ticketing_system/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── tickets/
│   ├── migrations/
│   ├── static/
│   ├── templates/
│   ├── admin.py
│   ├── forms.py
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── backends.py
│   ├── payment_observer.py
│   ├── signals.py
│   └── utils.py
│
├── manage.py
├── .gitignore
└── README.md


---

## 🚀 Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/shaydarkstar-game/university-ticketing-system.git
cd university-ticketing-system