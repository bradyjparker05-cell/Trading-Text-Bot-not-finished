import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(subject: str, html_body: str) -> None:
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    to_emails = [addr.strip() for addr in os.environ["TO_EMAIL"].split(",") if addr.strip()]

    msg = MIMEMultipart("alternative")
    msg["From"] = gmail_address
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, to_emails, msg.as_string())

    print(f"Sent to {', '.join(to_emails)}")
