from data_fetcher import fetch_all
from email_builder import build_email
from email_sender import send_email


def main():
    data = fetch_all()
    subject, html = build_email(data)
    send_email(subject, html)


if __name__ == "__main__":
    main()
