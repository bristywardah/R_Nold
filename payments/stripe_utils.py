import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(product, customer, success_url, cancel_url):
    price_to_use = product.price1

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": product.name},
                "unit_amount": int(price_to_use * 100), 
            },
            "quantity": 1,
        }],
        mode="payment",
        customer_email=customer.email,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "product_id": str(product.id),
            "customer_id": str(customer.id),
            "vendor_id": str(product.vendor.id),
            "payment": "true",
        },
    )
    return session
