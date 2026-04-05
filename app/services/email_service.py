import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def send_po_email(vendor_name: str, vendor_email: str, po_id: str, item_name: str, quantity: int):
    """
    Sends a Purchase Order notification email to the vendor.
    Uses SMTP credentials from environment variables.
    Returns a dict with status info.
    """

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user)
    company_name = os.getenv("COMPANY_NAME", "Thaikkattu Mooss Vaidyaratnam")

    if not smtp_user or not smtp_password:
        print(f"[EMAIL] SMTP not configured. Skipping email to {vendor_email}")
        return {
            "email_sent": False,
            "reason": "SMTP credentials not configured in .env"
        }

    if not vendor_email:
        print(f"[EMAIL] No email address for vendor '{vendor_name}'. Skipping.")
        return {
            "email_sent": False,
            "reason": f"No email address on file for vendor '{vendor_name}'"
        }

    # Build the email
    subject = f"New Purchase Order #{po_id} from {company_name}"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #1a5276, #2e86c1); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="color: #fff; margin: 0; font-size: 24px;">{company_name}</h1>
            <p style="color: #d5e8f0; margin: 5px 0 0 0; font-size: 14px;">Purchase Order Notification</p>
        </div>

        <div style="background: #fff; padding: 30px; border: 1px solid #e0e0e0;">
            <p>Dear <strong>{vendor_name.title()}</strong>,</p>

            <p>A new purchase order has been created and requires your attention:</p>

            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="background: #f7f9fc;">
                    <td style="padding: 12px; border: 1px solid #e0e0e0; font-weight: bold; width: 40%;">PO Number</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0;">#{po_id}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; font-weight: bold;">Item</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0;">{item_name.title()}</td>
                </tr>
                <tr style="background: #f7f9fc;">
                    <td style="padding: 12px; border: 1px solid #e0e0e0; font-weight: bold;">Quantity</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0;">{quantity}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; font-weight: bold;">Date</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0;">{datetime.now().strftime('%B %d, %Y')}</td>
                </tr>
                <tr style="background: #f7f9fc;">
                    <td style="padding: 12px; border: 1px solid #e0e0e0; font-weight: bold;">Status</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0;">
                        <span style="background: #f39c12; color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 12px;">Pending</span>
                    </td>
                </tr>
            </table>

            <p>Please confirm acceptance and arrange delivery at the earliest.</p>

            <p style="margin-top: 30px; color: #888; font-size: 12px;">
                This is an automated notification from the {company_name} ERP System.<br>
                Please do not reply directly to this email.
            </p>
        </div>

        <div style="background: #f0f0f0; padding: 15px; text-align: center; border-radius: 0 0 10px 10px; font-size: 11px; color: #999;">
            &copy; {datetime.now().year} {company_name} &mdash; ERP AI Agent
        </div>
    </body>
    </html>
    """

    plain_body = f"""
Purchase Order Notification — {company_name}
=============================================

Dear {vendor_name.title()},

A new purchase order has been created:

  PO Number: #{po_id}
  Item:      {item_name.title()}
  Quantity:  {quantity}
  Date:      {datetime.now().strftime('%B %d, %Y')}
  Status:    Pending

Please confirm acceptance and arrange delivery.

—
{company_name} ERP System (Automated)
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = vendor_email
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, vendor_email, msg.as_string())

        print(f"[EMAIL] ✅ PO #{po_id} notification sent to {vendor_email}")
        return {
            "email_sent": True,
            "recipient": vendor_email,
            "po_id": po_id
        }

    except Exception as e:
        print(f"[EMAIL] ❌ Failed to send email to {vendor_email}: {e}")
        return {
            "email_sent": False,
            "reason": str(e)
        }


def send_po_cancellation_email(
    vendor_name: str,
    vendor_email: str,
    po_id: str,
    item_name: str,
    quantity: int,
    cancellation_reason: str | None = None,
):
    """
    Sends a Purchase Order cancellation email to the vendor.
    Uses SMTP credentials from environment variables.
    Returns a dict with status info.
    """

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user)
    company_name = os.getenv("COMPANY_NAME", "Thaikkattu Mooss Vaidyaratnam")
    reason_text = (cancellation_reason or "No additional reason provided.").strip()

    if not smtp_user or not smtp_password:
        print(f"[EMAIL] SMTP not configured. Skipping cancellation email to {vendor_email}")
        return {
            "email_sent": False,
            "reason": "SMTP credentials not configured in .env"
        }

    if not vendor_email:
        print(f"[EMAIL] No email address for vendor '{vendor_name}'. Skipping cancellation email.")
        return {
            "email_sent": False,
            "reason": f"No email address on file for vendor '{vendor_name}'"
        }

    subject = f"Purchase Order #{po_id} Cancelled - {company_name}"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #7f1d1d, #b91c1c); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="color: #fff; margin: 0; font-size: 24px;">{company_name}</h1>
            <p style="color: #fde2e2; margin: 5px 0 0 0; font-size: 14px;">Purchase Order Cancellation Notice</p>
        </div>

        <div style="background: #fff; padding: 30px; border: 1px solid #e0e0e0;">
            <p>Dear <strong>{vendor_name.title()}</strong>,</p>

            <p>Please note that the following purchase order has been cancelled:</p>

            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="background: #f7f9fc;">
                    <td style="padding: 12px; border: 1px solid #e0e0e0; font-weight: bold; width: 40%;">PO Number</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0;">#{po_id}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; font-weight: bold;">Item</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0;">{item_name.title()}</td>
                </tr>
                <tr style="background: #f7f9fc;">
                    <td style="padding: 12px; border: 1px solid #e0e0e0; font-weight: bold;">Quantity</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0;">{quantity}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; font-weight: bold;">Cancelled On</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0;">{datetime.now().strftime('%B %d, %Y %I:%M %p')}</td>
                </tr>
                <tr style="background: #f7f9fc;">
                    <td style="padding: 12px; border: 1px solid #e0e0e0; font-weight: bold;">Reason</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0;">{reason_text}</td>
                </tr>
            </table>

            <p>Please ignore this PO in your processing queue.</p>

            <p style="margin-top: 30px; color: #888; font-size: 12px;">
                This is an automated notification from the {company_name} ERP System.<br>
                Please do not reply directly to this email.
            </p>
        </div>

        <div style="background: #f0f0f0; padding: 15px; text-align: center; border-radius: 0 0 10px 10px; font-size: 11px; color: #999;">
            &copy; {datetime.now().year} {company_name} &mdash; ERP AI Agent
        </div>
    </body>
    </html>
    """

    plain_body = f"""
Purchase Order Cancellation Notice â€” {company_name}
===================================================

Dear {vendor_name.title()},

The following purchase order has been cancelled:

  PO Number:     #{po_id}
  Item:          {item_name.title()}
  Quantity:      {quantity}
  Cancelled On:  {datetime.now().strftime('%B %d, %Y %I:%M %p')}
  Reason:        {reason_text}

Please ignore this PO in your processing queue.

â€”
{company_name} ERP System (Automated)
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = vendor_email
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, vendor_email, msg.as_string())

        print(f"[EMAIL] âœ… PO #{po_id} cancellation notification sent to {vendor_email}")
        return {
            "email_sent": True,
            "recipient": vendor_email,
            "po_id": po_id
        }
    except Exception as e:
        print(f"[EMAIL] âŒ Failed to send cancellation email to {vendor_email}: {e}")
        return {
            "email_sent": False,
            "reason": str(e)
        }
