import smtplib
import os
from email.mime.text import MIMEText


def send_sms(message_body: str) -> None:
    gmail_address  = os.environ["GMAIL_ADDRESS"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    phone_number   = os.environ["PHONE_NUMBER"]
    sms_gateway    = f"{phone_number}@tmomail.net"

    msg = MIMEText(message_body)
    msg["From"]    = gmail_address
    msg["To"]      = sms_gateway
    msg["Subject"] = ""

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, sms_gateway, msg.as_string())

    print(f"Sent to {sms_gateway}")
