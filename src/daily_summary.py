import os
from datetime import datetime, timedelta
from slack_sdk.web import WebClient
from dotenv import load_dotenv
import logging
from src.generate_summary import generate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


def get_yesterday_messages(client: WebClient, channel_id: str) -> list:
    """Fetch messages from the last 24 hours for a channel"""
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    oldest = yesterday.timestamp()

    messages = []
    try:
        result = client.conversations_history(
            channel=channel_id, oldest=oldest, limit=1000
        )

        if result["ok"]:
            # Add channel context to each message
            channel_info = client.conversations_info(channel=channel_id)
            channel_name = channel_info["channel"]["name"]

            for msg in result["messages"]:
                msg["channel_name"] = channel_name
                msg["channel_id"] = channel_id

            messages = result["messages"]

    except Exception as e:
        logger.error(f"Error fetching messages: {e}")

    return messages


def format_newsletter(all_messages: list) -> str:
    """Format all messages into a single newsletter"""

    now = datetime.now()
    newsletter = "*Daily Channel Summary*\n"
    newsletter += f"*Date:* {now.strftime('%Y-%m-%d')}\n"
    newsletter += "*Period:* Last 24 hours\n\n"

    if not all_messages:
        newsletter += "_No messages in any monitored channels in the last 24 hours_"
        return newsletter

    # Group messages by assessment type
    action_required = []
    acknowledge = []

    # Generate summaries for all messages at once
    summaries = generate(all_messages)

    # Process each message with its summary
    for msg, summary_data in zip(all_messages, summaries):
        # Add channel context and message details to summary
        summary_data["channel"] = msg["channel_name"]
        summary_data["ts"] = msg["ts"]
        summary_data["channel_id"] = msg["channel_id"]

        # Add files information
        if "files" in msg:
            summary_data["files"] = [
                {
                    "type": f.get("filetype", "").lower(),
                    "title": f.get("title", "Untitled"),
                    "url": f.get("url_private", ""),
                }
                for f in msg["files"]
            ]

        if summary_data["assessment"] == "Action required":
            action_required.append(summary_data)
        elif summary_data["assessment"] == "Acknowledge":
            acknowledge.append(summary_data)

    # Format action required messages
    if action_required:
        newsletter += "*🚨 Action Required Items:*\n"
        for msg in action_required:
            permalink = get_message_link(msg["channel_id"], msg["ts"])
            newsletter += f"• [#{msg['channel']}] {msg['summary']}\n"

            # Add file links if present
            if "files" in msg:
                for file in msg["files"]:
                    newsletter += f"  📎 {file['title']} ({file['type'].upper()})\n"

            newsletter += f"  <{permalink}|View message>\n"
        newsletter += "\n"

    # Format acknowledgment messages similarly
    if acknowledge:
        newsletter += "*📝 Other Updates:*\n"
        for msg in acknowledge:
            permalink = get_message_link(msg["channel_id"], msg["ts"])
            newsletter += f"• [#{msg['channel']}] {msg['summary']}\n"

            # Add file links if present
            if "files" in msg:
                for file in msg["files"]:
                    newsletter += f"  📎 {file['title']} ({file['type'].upper()})\n"

            newsletter += f"  <{permalink}|View message>\n"

    # Add summary statistics
    newsletter += "\n*Summary Statistics:*\n"
    newsletter += f"• Action items: {len(action_required)}\n"
    newsletter += f"• Updates: {len(acknowledge)}\n"
    newsletter += f"• Total messages processed: {len(all_messages)}\n"

    return newsletter


def get_message_link(channel_id: str, message_ts: str) -> str:
    """Get permalink to a message"""
    client = WebClient(token=os.environ["SLACK_BOT_USER_TOKEN"])
    try:
        result = client.chat_getPermalink(channel=channel_id, message_ts=message_ts)
        return result["permalink"]
    except Exception as e:
        logger.error(f"Error getting permalink: {e}")
        return "Link unavailable"


def send_daily_summary():
    """Main function to generate and send daily newsletter"""
    client = WebClient(token=os.environ["SLACK_BOT_USER_TOKEN"])

    MONITORED_CHANNELS = os.environ.get("MONITORED_CHANNEL_IDS", "").split(",")
    SUMMARY_CHANNEL = os.environ.get("SUMMARY_CHANNEL_ID")

    # Collect messages from all channels
    all_messages = []
    for channel_id in MONITORED_CHANNELS:
        try:
            messages = get_yesterday_messages(client, channel_id)
            all_messages.extend(messages)
        except Exception as e:
            logger.error(f"Error processing channel {channel_id}: {e}")

    # Generate and send the newsletter
    try:
        newsletter = format_newsletter(all_messages)

        client.chat_postMessage(
            channel=SUMMARY_CHANNEL, text=newsletter, unfurl_links=False
        )

        logger.info("Sent daily newsletter")

    except Exception as e:
        logger.error(f"Error sending newsletter: {e}")


if __name__ == "__main__":
    send_daily_summary()
