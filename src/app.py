import os
from slack_sdk.web import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from dotenv import load_dotenv
from src.generate_summary import generate
import logging
from threading import Event
import requests
import base64

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Get channels to monitor from environment variable (comma-separated list)
MONITORED_CHANNELS = os.environ.get("MONITORED_CHANNEL_IDS", "").split(",")
SUMMARY_CHANNEL = os.environ.get("SUMMARY_CHANNEL_ID")


def format_summary_message(summary_data, channel_name, message_link):
    """Format the summary message based on the response data"""
    message = f"*New message in #{channel_name}*:\n"
    message += f"<{message_link}|View original message>\n\n"
    message += f"*Summary:* {summary_data['summary']}\n"
    message += f"*Assessment:* {summary_data['assessment']}"
    return message


def process(client: SocketModeClient, req: SocketModeRequest):
    if req.type == "events_api":
        # Acknowledge the request
        response = SocketModeResponse(envelope_id=req.envelope_id)
        client.send_socket_mode_response(response)

        # Process message events
        if req.payload["event"]["type"] == "message" and (
            req.payload["event"].get("subtype") is None
            or req.payload["event"].get("subtype") == "file_share"
        ):
            event = req.payload["event"]

            channel_id = event["channel"]

            # Ignore messages from the summary channel and bot messages
            if channel_id == SUMMARY_CHANNEL or "bot_id" in event:
                return

            # Only process messages from monitored channels
            if channel_id not in MONITORED_CHANNELS:
                return

            # Get channel info
            channel_info = client.web_client.conversations_info(channel=channel_id)
            channel_name = channel_info["channel"]["name"]

            # Get message permalink
            permalink_response = client.web_client.chat_getPermalink(
                channel=channel_id, message_ts=event["ts"]
            )
            message_link = permalink_response["permalink"]

            # Format the message text and handle any files
            message_text = f"{event.get('user', 'unknown')}: {event['text']}"

            # Initialize list for images
            message_images = []

            # Handle files if present
            if "files" in event:
                for file in event["files"]:
                    file_type = file.get("filetype", "").lower()
                    file_url = file.get("url_private")

                    if file_type in ["pdf", "png", "jpg", "jpeg"]:
                        # Download file with auth
                        headers = {
                            "Authorization": f"Bearer {os.environ['SLACK_BOT_USER_TOKEN']}"
                        }
                        response = requests.get(file_url, headers=headers)

                        if response.status_code == 200:
                            # For PDFs
                            if file_type == "pdf":
                                message_text += (
                                    f"\n[PDF Content: {file.get('title', 'Untitled')}]"
                                )
                                # TODO: Add PDF text extraction if needed

                            # For images
                            elif file_type in ["png", "jpg", "jpeg"]:
                                # Convert image to base64 for Gemini
                                image_base64 = base64.b64encode(
                                    response.content
                                ).decode()

                                message_text += (
                                    f"\n[Image: {file.get('title', 'Untitled')}]"
                                )
                                # Store image for Gemini
                                message_images.append(
                                    {
                                        "mime_type": file.get("mimetype", "image/jpeg"),
                                        "data": image_base64,
                                    }
                                )

            # Generate summary for this message
            summary_data = generate(message_text, images=message_images)

            # Handle different assessment types
            assessment = summary_data.get("assessment", "Acknowledge")

            if assessment == "Ignore":
                return  # Don't send any message

            formatted_message = format_summary_message(
                summary_data, channel_name, message_link
            )

            if assessment == "Action required":
                # Add @channel mention for important messages
                formatted_message = "<!channel>\n" + formatted_message

            # Send summary to the summary channel
            client.web_client.chat_postMessage(
                channel=SUMMARY_CHANNEL,
                text=formatted_message,
            )


if __name__ == "__main__":
    # Initialize SocketModeClient
    client = SocketModeClient(
        app_token=os.environ["SLACK_APP_TOKEN"],
        web_client=WebClient(token=os.environ["SLACK_BOT_USER_TOKEN"]),
    )

    # Add the message processor
    client.socket_mode_request_listeners.append(process)

    # Connect to Slack
    client.connect()

    # Keep the app running
    Event().wait()
