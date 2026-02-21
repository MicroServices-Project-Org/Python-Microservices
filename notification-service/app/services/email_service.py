import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings


async def send_email(to_email: str, subject: str, body_html: str) -> bool:
    """
    Send an email via Gmail SMTP.
    If EMAIL_ENABLED is False, logs the email instead of sending.
    """
    if not settings.EMAIL_ENABLED:
        print(
            f"📧 [EMAIL DISABLED] Would send to={to_email} subject='{subject}'\n"
            f"Body:\n{body_html}"
        )
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)

        print(f"✅ Email sent to {to_email}: {subject}")
        return True

    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {e}")
        return False


# ─── Email Template Builders ─────────────────────────────────────────────────

def build_order_confirmation_email(event: dict) -> tuple[str, str]:
    """Returns (subject, body_html) for order confirmation."""
    items_rows = ""
    for item in event.get("items", []):
        items_rows += (
            f"<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{item['product_name']}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{item['quantity']}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>${item['price']:.2f}</td>"
            f"</tr>"
        )

    subject = f"Order Confirmed — {event['order_number']}"
    body = f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
        <h2 style="color:#2d3748">Order Confirmed! ✅</h2>
        <p>Hi {event['customer_name']},</p>
        <p>Your order <strong>{event['order_number']}</strong> has been confirmed.</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
            <tr style="background:#f7fafc">
                <th style="padding:8px;text-align:left">Product</th>
                <th style="padding:8px;text-align:left">Qty</th>
                <th style="padding:8px;text-align:left">Price</th>
            </tr>
            {items_rows}
        </table>
        <p style="font-size:18px"><strong>Total: ${event['total_amount']:.2f}</strong></p>
        <p style="color:#718096;font-size:14px">Thank you for shopping with us!</p>
    </body>
    </html>
    """
    return subject, body


def build_order_cancelled_email(event: dict) -> tuple[str, str]:
    """Returns (subject, body_html) for order cancellation."""
    subject = f"Order Cancelled — {event['order_number']}"
    body = f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
        <h2 style="color:#e53e3e">Order Cancelled</h2>
        <p>Hi {event['customer_name']},</p>
        <p>Your order <strong>{event['order_number']}</strong> has been cancelled.</p>
        <p>If you did not request this, please contact our support team.</p>
        <p style="color:#718096;font-size:14px">We hope to see you again soon.</p>
    </body>
    </html>
    """
    return subject, body


def build_inventory_low_email(event: dict) -> tuple[str, str]:
    """Returns (subject, body_html) for low stock alert (sent to admin)."""
    subject = f"⚠️ Low Stock Alert — {event.get('product_name', 'Unknown Product')}"
    body = f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
        <h2 style="color:#d69e2e">Low Stock Alert ⚠️</h2>
        <p>Product <strong>{event.get('product_name', 'N/A')}</strong>
           (ID: {event.get('product_id', 'N/A')}) is running low.</p>
        <p>Current quantity: <strong>{event.get('quantity', 'N/A')}</strong></p>
        <p>Please restock soon to avoid stockouts.</p>
    </body>
    </html>
    """
    return subject, body