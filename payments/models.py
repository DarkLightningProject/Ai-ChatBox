import uuid
from django.db import models
from django.contrib.auth.models import User


class Order(models.Model):
    STATUS_CREATED = "created"
    STATUS_INITIATED = "payment_initiated"
    STATUS_CAPTURED = "captured"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_CREATED, "Created"),
        (STATUS_INITIATED, "Payment Initiated"),
        (STATUS_CAPTURED, "Captured"),
        (STATUS_FAILED, "Failed"),
    ]

    # Internal primary key — never exposed to frontend
    id = models.BigAutoField(primary_key=True)

    # Razorpay-issued order ID (e.g. "order_XXXXX") — db-indexed for fast webhook lookups
    order_id = models.CharField(max_length=100, unique=True, db_index=True)

    # Set only after successful payment capture
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)

    # Amount in paise (₹100 = 10000 paise). Stored to defend against price-tampering.
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=10, default="INR")

    # receipt is a short string we generate; useful for reconciliation
    receipt = models.CharField(max_length=100)

    # null=True so unauthenticated/guest payments are still tracked
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )

    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default=STATUS_CREATED, db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order_id} | ₹{self.amount // 100} | {self.status}"
