from market_scanner import get_market_sentiment, build_sms
from sms_sender import send_sms


def main():
    results = get_market_sentiment()
    message = build_sms(results)
    print(message)
    send_sms(message)


if __name__ == "__main__":
    main()
