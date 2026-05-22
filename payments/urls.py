from django.urls import path
from .views import BillingStatusView, CreateOrderView, RazorpayWebhookView, VerifyPaymentView

urlpatterns = [
    path("create-order/", CreateOrderView.as_view(), name="payment-create-order"),
    path("verify-payment/", VerifyPaymentView.as_view(), name="payment-verify"),
    path("billing-status/", BillingStatusView.as_view(), name="payment-billing-status"),
    path("webhook/razorpay/", RazorpayWebhookView.as_view(), name="payment-webhook"),
]
