"""
Razorpay payment views.

Security contract:
  - order_id is NEVER generated or trusted from the frontend.
  - Every order is persisted to DB before its ID is returned.
  - Signature verification uses HMAC-SHA256 with server-side secret.
  - Amount is re-validated against the DB record on every verify call.
  - Webhook handler is idempotent and verifies its own signature.
"""

import hashlib
import hmac
import json
import logging
import os
import uuid

import razorpay
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from accounts.models import Profile
from .models import Order

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GET /api/payments/billing-status/
# ---------------------------------------------------------------------------
class BillingStatusView(APIView):
    """
    Returns the current user's premium status and source.

    Response:
      {
        "is_premium": bool,
        "source": "payment" | "admin_grant" | null,
        "premium_granted_at": ISO-string | null,
        "order": { order_id, razorpay_payment_id, amount, currency, created_at } | null
      }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = request.user.profile
            is_premium = profile.is_premium
            premium_granted_at = profile.premium_granted_at
        except Profile.DoesNotExist:
            is_premium = False
            premium_granted_at = None

        latest_order = (
            Order.objects.filter(user=request.user, status=Order.STATUS_CAPTURED)
            .order_by("-created_at")
            .first()
        )

        if not is_premium:
            source = None
        elif latest_order:
            source = "payment"
        else:
            source = "admin_grant"

        order_data = None
        if latest_order:
            order_data = {
                "order_id": latest_order.order_id,
                "razorpay_payment_id": latest_order.razorpay_payment_id,
                "amount": latest_order.amount,
                "currency": latest_order.currency,
                "created_at": latest_order.created_at.isoformat(),
            }

        return Response({
            "is_premium": is_premium,
            "source": source,
            "premium_granted_at": premium_granted_at.isoformat() if premium_granted_at else None,
            "order": order_data,
        })

# ---------------------------------------------------------------------------
# Razorpay client (reads keys from env — never from request)
# ---------------------------------------------------------------------------
_RZP_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
_RZP_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")

razorpay_client = razorpay.Client(auth=(_RZP_KEY_ID, _RZP_KEY_SECRET))


def _grant_premium(user):
    """Mark the user's profile as premium. Safe to call multiple times."""
    if user is None:
        return
    try:
        profile, _ = Profile.objects.get_or_create(user=user)
        if not profile.is_premium:
            profile.is_premium = True
            profile.premium_granted_at = timezone.now()
            profile.save(update_fields=["is_premium", "premium_granted_at"])
            logger.info("Premium granted to user=%s", user.id)
    except Exception as exc:
        logger.error("Failed to grant premium to user=%s: %s", user.id, exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Return True if the Razorpay HMAC-SHA256 signature is valid."""
    message = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(
        _RZP_KEY_SECRET.encode(), message, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Return True if the webhook X-Razorpay-Signature is valid."""
    webhook_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    if not webhook_secret:
        logger.warning("RAZORPAY_WEBHOOK_SECRET is not set — rejecting webhook")
        return False
    expected = hmac.new(
        webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# POST /api/payments/create-order/
# ---------------------------------------------------------------------------
class CreateOrderView(APIView):
    """
    Creates a Razorpay order server-side and persists it before responding.

    Request body:
        { "amount": <int paise>, "currency": "INR" }   (currency optional)

    Response:
        { "order_id": "order_XXX", "amount": 49900, "currency": "INR" }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # --- 1. Validate amount ------------------------------------------------
        try:
            amount = int(request.data.get("amount", 0))
        except (TypeError, ValueError):
            return Response(
                {"error": "amount must be an integer (paise)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount < 100:  # minimum ₹1 = 100 paise
            return Response(
                {"error": "amount must be at least 100 paise (₹1)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount > 500_000_00:  # ₹5,00,000 cap — adjust to your business logic
            return Response(
                {"error": "amount exceeds maximum allowed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        currency = request.data.get("currency", "INR").upper()
        if currency not in {"INR"}:  # expand as needed
            return Response(
                {"error": "unsupported currency"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- 2. Create order via Razorpay API ----------------------------------
        receipt = f"rcpt_{uuid.uuid4().hex[:16]}"
        try:
            rzp_order = razorpay_client.order.create(
                {
                    "amount": amount,
                    "currency": currency,
                    "receipt": receipt,
                    "payment_capture": 1,  # auto-capture
                }
            )
        except Exception as exc:
            logger.error("Razorpay order creation failed: %s", exc)
            return Response(
                {"error": "could not create payment order"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        rzp_order_id = rzp_order["id"]

        # --- 3. Persist to DB BEFORE returning order_id to frontend -----------
        try:
            order = Order.objects.create(
                order_id=rzp_order_id,
                amount=amount,
                currency=currency,
                receipt=receipt,
                user=request.user,
                status=Order.STATUS_CREATED,
            )
        except Exception as exc:
            logger.error("Failed to save order %s to DB: %s", rzp_order_id, exc)
            return Response(
                {"error": "order could not be recorded"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info("Order created: order_id=%s user=%s", order.order_id, request.user.id)

        # --- 4. Return minimal payload — key_id needed to init checkout.js ---
        return Response(
            {
                "order_id": rzp_order_id,
                "amount": amount,
                "currency": currency,
                "key_id": _RZP_KEY_ID,  # public key — safe to expose
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# POST /api/payments/verify-payment/
# ---------------------------------------------------------------------------
class VerifyPaymentView(APIView):
    """
    Verifies a completed Razorpay payment.

    Steps (all on server):
      1. Look up order_id in our DB — reject if not found.
      2. Verify HMAC-SHA256 signature.
      3. Fetch payment from Razorpay and confirm `captured` status.
      4. Confirm paid amount matches stored order amount.
      5. Update order status to `captured`.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get("razorpay_payment_id", "").strip()
        order_id = request.data.get("razorpay_order_id", "").strip()
        signature = request.data.get("razorpay_signature", "").strip()

        if not all([payment_id, order_id, signature]):
            return Response(
                {"error": "razorpay_payment_id, razorpay_order_id, razorpay_signature are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- 1. Look up order in OUR database ---------------------------------
        try:
            order = Order.objects.get(order_id=order_id, user=request.user)
        except Order.DoesNotExist:
            logger.warning(
                "verify-payment: unknown order_id=%s user=%s", order_id, request.user.id
            )
            return Response(
                {"error": "order not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Idempotent — already successfully captured
        if order.status == Order.STATUS_CAPTURED:
            return Response({"status": "already_captured"}, status=status.HTTP_200_OK)

        # Mark as initiated so we can track partial states
        order.status = Order.STATUS_INITIATED
        order.razorpay_payment_id = payment_id
        order.save(update_fields=["status", "razorpay_payment_id", "updated_at"])

        # --- 2. Verify HMAC-SHA256 signature -----------------------------------
        if not _verify_signature(order_id, payment_id, signature):
            logger.warning(
                "verify-payment: invalid signature order_id=%s payment_id=%s",
                order_id,
                payment_id,
            )
            order.status = Order.STATUS_FAILED
            order.save(update_fields=["status", "updated_at"])
            return Response(
                {"error": "signature verification failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- 3. Fetch payment from Razorpay to confirm capture ----------------
        try:
            rzp_payment = razorpay_client.payment.fetch(payment_id)
        except Exception as exc:
            logger.error(
                "verify-payment: Razorpay fetch failed payment_id=%s: %s", payment_id, exc
            )
            return Response(
                {"error": "could not verify payment with Razorpay"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if rzp_payment.get("status") != "captured":
            logger.warning(
                "verify-payment: payment not captured payment_id=%s status=%s",
                payment_id,
                rzp_payment.get("status"),
            )
            order.status = Order.STATUS_FAILED
            order.save(update_fields=["status", "updated_at"])
            return Response(
                {"error": "payment not captured"},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        # --- 4. Validate amount — prevent price tampering ---------------------
        if int(rzp_payment.get("amount", 0)) != order.amount:
            logger.error(
                "verify-payment: AMOUNT MISMATCH order_id=%s expected=%s got=%s",
                order_id,
                order.amount,
                rzp_payment.get("amount"),
            )
            order.status = Order.STATUS_FAILED
            order.save(update_fields=["status", "updated_at"])
            return Response(
                {"error": "amount mismatch — payment rejected"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- 5. All checks passed — mark as captured + grant premium ----------
        order.status = Order.STATUS_CAPTURED
        order.save(update_fields=["status", "updated_at"])

        _grant_premium(request.user)

        logger.info(
            "Payment captured: order_id=%s payment_id=%s user=%s",
            order_id,
            payment_id,
            request.user.id,
        )

        return Response(
            {
                "status": "captured",
                "order_id": order_id,
                "payment_id": payment_id,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# POST /api/payments/webhook/razorpay/
# Exempt from CSRF — Razorpay calls this from their servers (no browser cookie)
# ---------------------------------------------------------------------------
@method_decorator(csrf_exempt, name="dispatch")
class RazorpayWebhookView(View):
    """
    Handles Razorpay webhook events.

    Security: verifies X-Razorpay-Signature on every request.
    Idempotent: skips orders already in `captured` state.
    """

    def post(self, request):
        body = request.body  # raw bytes needed for signature check

        # --- 1. Verify webhook signature --------------------------------------
        signature = request.headers.get("X-Razorpay-Signature", "")
        if not _verify_webhook_signature(body, signature):
            logger.warning("Webhook: invalid signature — rejected")
            return JsonResponse({"error": "invalid signature"}, status=400)

        # --- 2. Parse payload -------------------------------------------------
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid JSON"}, status=400)

        event = payload.get("event")
        entity = payload.get("payload", {})

        logger.info("Webhook received: event=%s", event)

        # --- 3. Route by event type -------------------------------------------
        if event == "payment.captured":
            self._handle_payment_captured(entity)
        elif event == "order.paid":
            self._handle_order_paid(entity)
        elif event == "payment.failed":
            self._handle_payment_failed(entity)
        # Unknown events are silently ignored — return 200 so Razorpay stops retrying

        # Always return 200 immediately; Razorpay retries on non-2xx
        return JsonResponse({"status": "ok"}, status=200)

    # ------------------------------------------------------------------
    def _handle_payment_captured(self, entity: dict):
        payment = entity.get("payment", {}).get("entity", {})
        order_id = payment.get("order_id")
        payment_id = payment.get("id")
        amount = payment.get("amount")

        if not order_id:
            logger.warning("payment.captured: missing order_id in payload")
            return

        try:
            order = Order.objects.get(order_id=order_id)
        except Order.DoesNotExist:
            logger.warning("payment.captured: unknown order_id=%s", order_id)
            return

        # Idempotent
        if order.status == Order.STATUS_CAPTURED:
            logger.info("payment.captured: order already captured order_id=%s", order_id)
            return

        # Validate amount
        if amount and int(amount) != order.amount:
            logger.error(
                "payment.captured: AMOUNT MISMATCH order_id=%s expected=%s got=%s",
                order_id, order.amount, amount,
            )
            return

        order.status = Order.STATUS_CAPTURED
        order.razorpay_payment_id = payment_id
        order.save(update_fields=["status", "razorpay_payment_id", "updated_at"])
        _grant_premium(order.user)
        logger.info("payment.captured: captured order_id=%s payment_id=%s", order_id, payment_id)

    def _handle_order_paid(self, entity: dict):
        order_entity = entity.get("order", {}).get("entity", {})
        order_id = order_entity.get("id")

        if not order_id:
            return

        try:
            order = Order.objects.get(order_id=order_id)
        except Order.DoesNotExist:
            logger.warning("order.paid: unknown order_id=%s", order_id)
            return

        if order.status == Order.STATUS_CAPTURED:
            return  # idempotent

        order.status = Order.STATUS_CAPTURED
        order.save(update_fields=["status", "updated_at"])
        _grant_premium(order.user)
        logger.info("order.paid: marked captured order_id=%s", order_id)

    def _handle_payment_failed(self, entity: dict):
        payment = entity.get("payment", {}).get("entity", {})
        order_id = payment.get("order_id")
        payment_id = payment.get("id")

        if not order_id:
            return

        try:
            order = Order.objects.get(order_id=order_id)
        except Order.DoesNotExist:
            logger.warning("payment.failed: unknown order_id=%s", order_id)
            return

        if order.status in (Order.STATUS_CAPTURED,):
            return  # never downgrade a captured order

        order.status = Order.STATUS_FAILED
        order.razorpay_payment_id = payment_id
        order.save(update_fields=["status", "razorpay_payment_id", "updated_at"])
        logger.info("payment.failed: order_id=%s payment_id=%s", order_id, payment_id)
