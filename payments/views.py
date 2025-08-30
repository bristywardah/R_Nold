import logging
from decimal import Decimal
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
import stripe

from orders.models import Order
from users.models import User
from orders.enums import OrderStatus
from payments.models import Payment
from notification.utils import notify_order_payment_completed, notify_order_payment_cancelled

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


# ------------------------
# CHECKOUT SESSION
# ------------------------
class CheckoutViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='checkout')
    def checkout(self, request):
        order_id = request.data.get("order_id")
        if not order_id:
            return Response({"error": "order_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        order = get_object_or_404(Order, order_id=order_id, customer=request.user)
        return self.create_stripe_session(order, request.user)

    def create_stripe_session(self, order, user):
        line_items = []
        items_data = []

        for item in order.items.all():
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": item.product.name},
                    "unit_amount": int(Decimal(item.price) * 100),
                },
                "quantity": item.quantity,
            })
            items_data.append({
                "id": item.id,
                "product": {
                    "id": item.product.id,
                    "name": item.product.name,
                    "sku": getattr(item.product, "sku", ""),
                    "price": str(item.price),
                    "status": item.product.status,
                },
                "quantity": item.quantity,
                "price": str(item.price),
            })

        # Shipping addresses
        shipping_address = order.selected_shipping_address
        shipping_addresses_data = []
        if shipping_address:
            shipping_addresses_data.append({
                "id": shipping_address.id,
                "full_name": shipping_address.full_name,
                "phone_number": shipping_address.phone_number,
                "email": shipping_address.email,
                "street_address": shipping_address.street_address,
                "landmark": shipping_address.landmark,
                "apartment_name": shipping_address.apartment_name,
                "floor_number": shipping_address.floor_number,
                "flat_number": shipping_address.flat_number,
                "city": shipping_address.city,
                "zip_code": shipping_address.zip_code,
                "billing_same_as_shipping": shipping_address.billing_same_as_shipping,
            })

        # Frontend URLs fallback
        frontend_success_base = getattr(settings, "FRONTEND_PAYMENT_SUCCESS_URL", "http://localhost:5173/payments/success/")
        frontend_cancel = getattr(settings, "FRONTEND_PAYMENT_CANCEL_URL", "http://localhost:5173/payments/cancel/")
        frontend_success = f"{frontend_success_base}?order_id={order.order_id}"

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=line_items,
                mode="payment",
                customer_email=user.email,
                success_url=frontend_success,
                cancel_url=frontend_cancel,
                metadata={
                    "order_id": order.order_id,
                    "customer_id": str(user.id),
                    "vendor_id": str(order.vendor.id),
                },
            )

            response_data = {
                "checkout_url": session.url,
                "order_id": order.order_id,
                "total_amount": str(order.total_amount),
                "item_count": order.items.count(),
                "items": items_data,
                "vendor": {
                    "id": order.vendor.id,
                    "full_name": f"{order.vendor.first_name} {order.vendor.last_name}".strip(),
                    "email": order.vendor.email
                },
                "customer": {
                    "id": order.customer.id,
                    "full_name": f"{order.customer.first_name} {order.customer.last_name}".strip(),
                    "email": order.customer.email
                },
                "shipping_addresses": shipping_addresses_data,
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Stripe session creation failed: {e}", exc_info=True)
            return Response({"error": "Failed to create checkout session"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ------------------------
# STRIPE WEBHOOK
# ------------------------
class StripeWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        logger.info("Stripe webhook received")
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

        logger.debug(f"Payload: {payload}")
        logger.debug(f"Stripe Signature Header: {sig_header}")

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
            logger.info(f"Stripe event type: {event['type']}")
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid Stripe signature")
            return Response({"error": "Invalid signature"}, status=400)
        except Exception as e:
            logger.error(f"Stripe webhook error: {e}", exc_info=True)
            return Response({"error": "Webhook error"}, status=500)

        event_type = event["type"]
        session = event["data"]["object"]

        handlers = {
            "checkout.session.completed": self.handle_checkout_completed,
            "checkout.session.expired": self.handle_checkout_expired,
            "payment_intent.payment_failed": self.handle_payment_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            logger.info(f"Calling handler for event: {event_type}")
            return handler(session)

        logger.info(f"Unhandled Stripe event: {event_type}")
        return Response({"status": "event_not_handled"}, status=200)


    # ------------------------
    # HANDLERS
    # ------------------------
    def handle_checkout_completed(self, session):
        metadata = session.get("metadata", {})
        order_id = metadata.get("order_id")
        customer_id = metadata.get("customer_id")
        vendor_id = metadata.get("vendor_id")

        if not order_id:
            return Response({"error": "No order_id in metadata"}, status=400)

        try:
            order = Order.objects.get(order_id=order_id)
            customer = User.objects.get(id=customer_id)
            vendor = User.objects.get(id=vendor_id)
            amount = Decimal(session.get("amount_total", 0)) / 100

            Payment.objects.update_or_create(
                order=order,
                defaults={
                    "customer": customer,
                    "vendor": vendor,
                    "amount": amount,
                    "payment_method": "stripe",
                    "transaction_id": session.get("id"),
                    "status": "completed",
                }
            )

            order.payment_status = OrderStatus.PAID.value
            order.order_status = OrderStatus.PROCESSING.value
            order.save(update_fields=["payment_status", "order_status"])

            notify_order_payment_completed(order, sender=customer)

            logger.info(f"Stripe payment completed for order {order_id}")
            return Response({"status": "payment_processed"}, status=200)

        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found")
            return Response({"error": "Order not found"}, status=404)
        except Exception as e:
            logger.error(f"Payment processing failed: {e}", exc_info=True)
            return Response({"error": "Processing error"}, status=500)

    def handle_checkout_expired(self, session):
        metadata = session.get("metadata", {})
        order_id = metadata.get("order_id")

        if not order_id:
            return Response({"error": "No order_id in metadata"}, status=400)

        try:
            order = Order.objects.get(order_id=order_id)
            order.payment_status = OrderStatus.CANCELLED.value
            order.order_status = OrderStatus.CANCELLED.value
            order.save(update_fields=["payment_status", "order_status"])

            notify_order_payment_cancelled(order, sender=order.customer)

            logger.info(f"Stripe checkout expired/cancelled for order {order_id}")
            return Response({"status": "payment_cancelled"}, status=200)

        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found")
            return Response({"error": "Order not found"}, status=404)
        except Exception as e:
            logger.error(f"Payment cancellation failed: {e}", exc_info=True)
            return Response({"error": "Processing error"}, status=500)

    def handle_payment_failed(self, session):
        metadata = session.get("metadata", {})
        order_id = metadata.get("order_id")

        if not order_id:
            return Response({"error": "No order_id in metadata"}, status=400)

        try:
            order = Order.objects.get(order_id=order_id)
            order.payment_status = OrderStatus.FAILED.value
            order.order_status = OrderStatus.CANCELLED.value
            order.save(update_fields=["payment_status", "order_status"])

            notify_order_payment_cancelled(order, sender=order.customer)

            logger.info(f"Stripe payment failed for order {order_id}")
            return Response({"status": "payment_failed"}, status=200)

        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found")
            return Response({"error": "Order not found"}, status=404)
        except Exception as e:
            logger.error(f"Payment failed handler error: {e}", exc_info=True)
            return Response({"error": "Processing error"}, status=500)
