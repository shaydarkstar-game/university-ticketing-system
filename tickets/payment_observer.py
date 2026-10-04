from abc import ABC, abstractmethod
from .models import Ticket

# ==========================
# OBSERVER PATTERN
# ==========================
class Observer(ABC):
    @abstractmethod
    def update(self, payment):
        pass

class Subject(ABC):
    def __init__(self):
        self._observers = []

    def attach(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer):
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, payment):
        for observer in self._observers:
            try:
                observer.update(payment)
            except Exception as e:
                print(f"Observer {observer} failed: {e}")


# ==========================
# PAYMENT PROCESSOR
# ==========================
class PaymentProcessor(Subject):
    def process_payment(self, payment):
        try:
            # Simulate real payment logic
            payment.status = "Completed"
            payment.save()

            # Notify observers (Ticket Generator)
            self.notify(payment)

            return True
        except Exception as e:
            print(f"PaymentProcessor failed: {e}")
            payment.status = "Failed"
            payment.save()
            return False


# ==========================
# TICKET GENERATOR
# ==========================
class TicketGenerator(Observer):
    def update(self, payment):
        event = payment.event
        seat_count = Ticket.objects.filter(event=event).count() + 1
        seat_id = f"S{seat_count}"

        Ticket.objects.create(
            user=payment.user,
            event=event,
            seat_number=seat_id,
            price=event.price
        )