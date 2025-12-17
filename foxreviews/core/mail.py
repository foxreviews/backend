
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string


class SendMail:
    def __init__(  # noqa: PLR0913
        self,
        subject: str,
        body: str,
        to: list[str],
        from_email: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[str] | None = None,
    ):
        self.subject = subject
        self.body = body
        self.to = to
        self.from_email = from_email
        self.cc = cc
        self.bcc = bcc
        self.attachments = attachments or []

    def send(self):
        email = EmailMessage(
            subject=self.subject,
            body=self.body,
            from_email=self.from_email,
            to=self.to,
            cc=self.cc,
            bcc=self.bcc,
        )

        for attachment_path in self.attachments:
            email.attach_file(attachment_path)

        email.send()


def send_email_with_attachments(
    subject: str,
    body: str,
    recipients: list[str],
    attachments: list[dict] | None = None,
):
    """
    Send HTML email with file attachments.

    Args:
        subject: Email subject
        body: HTML email body
        recipients: List of recipient email addresses
        attachments: List of dicts with keys: filename, content (bytes), mimetype
    """
    email = EmailMessage(
        subject=subject,
        body=body,
        to=recipients,
    )
    email.content_subtype = "html"

    if attachments:
        for attachment in attachments:
            email.attach(
                filename=attachment["filename"],
                content=attachment["content"],
                mimetype=attachment.get("mimetype", "application/octet-stream"),
            )

    email.send()


def send_html_email(
    subject: str,
    template_name: str,
    context: dict,
    recipients: list[str],
    from_email: str | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachments: list[dict] | None = None,
):
    """
    Send HTML email using Django template.

    Args:
        subject: Email subject
        template_name: Path to email template (e.g., 'emails/booking_confirmation.html')
        context: Dictionary of variables to pass to the template
        recipients: List of recipient email addresses
        from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)
        cc: List of CC recipients
        bcc: List of BCC recipients
        attachments: List of dicts with keys: filename, content (bytes), mimetype
    """
    # Render HTML content
    html_content = render_to_string(template_name, context)

    # Create email
    email = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        cc=cc,
        bcc=bcc,
    )
    email.content_subtype = "html"

    # Add attachments
    if attachments:
        for attachment in attachments:
            email.attach(
                filename=attachment["filename"],
                content=attachment["content"],
                mimetype=attachment.get("mimetype", "application/octet-stream"),
            )

    email.send()


def get_email_context_base() -> dict:
    """
    Get base context for all emails (company info, links, etc.).

    Returns:
        Dictionary with common email variables
    """
    return {
        "site_name": "MadaBest",
        "site_url": settings.SITE_URL
        if hasattr(settings, "SITE_URL")
        else "https://madabest.com",
        "support_email": "support@madabest.com",
        "company_name": "MadaBest - Agence de Voyage Madagascar",
        "company_address": "Madagascar",
        "year": 2025,
    }
