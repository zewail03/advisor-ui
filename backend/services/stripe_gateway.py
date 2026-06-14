"""Stripe gateway (TEST mode) for student tuition payments.

Uses Stripe Checkout (hosted page) so card data never touches our servers —
the backend only creates a Checkout Session and later verifies it was paid.
No publishable key or webhook is required: we confirm on the success redirect by
retrieving the session. The `stripe` SDK is synchronous, so call these via
`asyncio.to_thread(...)` from async endpoints.
"""
from typing import Optional

from core.config import settings


def stripe_enabled() -> bool:
    return bool(settings.stripe_secret_key)


def _client():
    import stripe

    stripe.api_key = settings.stripe_secret_key
    return stripe


def create_checkout_session(
    *,
    amount_minor: int,
    currency: str,
    product_name: str,
    description: str,
    success_url: str,
    cancel_url: str,
    metadata: dict,
    customer_email: Optional[str] = None,
):
    """Create a hosted Checkout Session for a one-time tuition payment."""
    stripe = _client()
    return stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": currency.lower(),
                    "product_data": {"name": product_name, "description": description[:200]},
                    "unit_amount": amount_minor,  # smallest currency unit (e.g. piasters)
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        customer_email=customer_email or None,
    )


def retrieve_session(session_id: str):
    return _client().checkout.Session.retrieve(session_id)
