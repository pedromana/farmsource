from fastapi import APIRouter, Request


router = APIRouter(tags=["payments"])


@router.post("/stripe/webhook")
async def stripe_webhook_placeholder(request: Request):
    return {"status": "placeholder", "detail": "Stripe webhook verification will be added in a future phase."}
