import json
from google import genai
from google.genai import types


def generate(messages, images=None):
    """Generate summary for one or more messages"""
    client = genai.Client(
        vertexai=True,
        project="snbx-vml-vcdm",
        location="us-central1",
    )

    # Format messages for the prompt, including files and links
    def format_message(msg):
        base_text = f"Message: {msg['text']}"

        # Add files information if present
        if "files" in msg:
            for file in msg["files"]:
                file_type = file.get("filetype", "").lower()
                title = file.get("title", "Untitled")
                if file_type in ["pdf", "png", "jpg", "jpeg"]:
                    base_text += f"\n[File: {file_type.upper()} - {title}]"

        return base_text

    formatted_messages = (
        "\n".join([format_message(msg) for msg in messages])
        if isinstance(messages, list)
        else format_message(messages)
    )

    # Create the text content with examples including files
    text = f"""input: Message: Critical security update needed for all GCP instances by EOD
[File: PDF - Security_Update.pdf]
Message: Team meeting tomorrow at 10 AM
[File: PNG - Meeting_Schedule.png]
output: [
  {{"summary": "Urgent security patches required for GCP instances, includes detailed PDF", "assessment": "Action required"}},
  {{"summary": "Team meeting scheduled for tomorrow at 10 AM, schedule image attached", "assessment": "Acknowledge"}}
]

input: {formatted_messages}
output: """

    # Create content parts
    parts = [{"text": text}]

    # Add images if present
    if images:
        parts.extend(
            [
                {"inline_data": {"mime_type": img["mime_type"], "data": img["data"]}}
                for img in images
            ]
        )

    # Create the content parts directly
    contents = [types.Content(role="user", parts=parts)]

    textsi_1 = """You are an intelligent assistant designed to manage and summarize Slack messages. Your task is to analyze each message and provide a summary and assessment.

1. **Summarization:**
  - Provide a concise summary of each message's content
  - Include key points and actions required
  - Summarize each message in 1 sentence
  - If a message includes a link or file, note that in the summary

2. **Assessment for each message:**
  - **Action required:**
   - If the message concerns our team, Visma Machine Learning (VML)
   - If it relates to our tech stack (Python, Golang, GCP, Kubernetes)
   - If there is a corporate-wide policy change
   - If it directly concerns VML team
   - If it directly concerns the VML team products - Smartscan and Autosuggest
  - **Acknowledge:** If the message is informative and only needs a brief acknowledgment
  - **Ignore:** For all other messages that do not require any action or acknowledgment

IMPORTANT: Respond with a JSON array containing an object for each message. Each object should have 'summary' and 'assessment' fields. The response must be valid JSON that can be parsed by Python's json.loads().

Example response format for multiple messages:
[
  {
    "summary": "First message summary",
    "assessment": "Action required"
  },
  {
    "summary": "Second message summary",
    "assessment": "Acknowledge"
  }
]

For a single message, still use an array with one object:
[
  {
    "summary": "Message summary",
    "assessment": "Ignore"
  }
]"""

    model = "gemini-2.0-flash-exp"

    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        max_output_tokens=8192,
        response_modalities=["TEXT"],
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"
            ),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
        system_instruction=[{"text": textsi_1}],
    )

    # Collect all text parts from the response
    full_response = ""
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        if chunk.candidates:
            for part in chunk.candidates[0].content.parts:
                if part.text:
                    full_response += part.text

    # Clean up the response - remove any markdown formatting
    full_response = full_response.strip()
    if full_response.startswith("```json"):
        full_response = full_response[7:]
    if full_response.startswith("```"):
        full_response = full_response[3:]
    if full_response.endswith("```"):
        full_response = full_response[:-3]

    full_response = full_response.strip()

    try:
        # Parse the response as JSON
        response_json = json.loads(full_response)
        return response_json
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {full_response}")
        print(f"Error: {e}")
        # Fallback in case of invalid JSON
        return {"summary": full_response, "assessment": "Acknowledge"}
