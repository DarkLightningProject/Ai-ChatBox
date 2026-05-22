from django.contrib import admin
from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id", "user_name", "user_email",
        "amount_rupees", "currency", "status",
        "razorpay_payment_id", "created_at",
    )
    list_filter = ("status", "currency", "created_at")
    search_fields = (
        "order_id", "razorpay_payment_id",
        "user__username", "user__email",
    )
    readonly_fields = (
        "order_id", "razorpay_payment_id", "amount", "currency",
        "receipt", "user", "created_at", "updated_at",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    fieldsets = (
        ("Order", {
            "fields": ("order_id", "receipt", "user", "status"),
        }),
        ("Amount", {
            "fields": ("amount", "currency"),
        }),
        ("Razorpay", {
            "fields": ("razorpay_payment_id",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def user_name(self, obj):
        return obj.user.username if obj.user else "—"
    user_name.short_description = "Username"
    user_name.admin_order_field = "user__username"

    def user_email(self, obj):
        return obj.user.email if obj.user else "—"
    user_email.short_description = "Email"
    user_email.admin_order_field = "user__email"

    def amount_rupees(self, obj):
        return f"₹{obj.amount / 100:.2f}"
    amount_rupees.short_description = "Amount"
    amount_rupees.admin_order_field = "amount"

    def has_add_permission(self, request):
        return False  # orders are only created via the API
