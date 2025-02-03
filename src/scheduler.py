import schedule
import time
from src.daily_summary import send_daily_summary
import logging
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_scheduler(run_now: bool = False):
    # Run immediately if requested
    if run_now:
        logger.info("Running summary now...")
        send_daily_summary()

    # Schedule the job to run at 8:00 AM every weekday
    schedule.every().monday.at("08:00").do(send_daily_summary)
    schedule.every().tuesday.at("08:00").do(send_daily_summary)
    schedule.every().wednesday.at("08:00").do(send_daily_summary)
    schedule.every().thursday.at("08:00").do(send_daily_summary)
    schedule.every().friday.at("08:00").do(send_daily_summary)

    logger.info("Scheduler started. Will run daily summaries at 8:00 AM on weekdays.")

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run the summary immediately before starting scheduler",
    )
    args = parser.parse_args()

    run_scheduler(run_now=args.now)
