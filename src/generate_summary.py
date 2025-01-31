import json
from google import genai
from google.genai import types


def generate(message, images=None):
    # Extract URLs from the message

    client = genai.Client(
        vertexai=True,
        project="snbx-vml-vcdm",
        location="us-central1",
    )

    # Create the text content
    text = f"""input: example input
output: example output

input: example input 2
output: example output 2


input: {message}
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
    contents = [
        types.Content(
            role="user",
            parts=parts,
        )
    ]

    textsi_1 = """You are an intelligent assistant designed to manage and summarize Slack messages within our organization's corporate global channels, including Security, AI, and others. Your tasks are as follows:

1. **Summarization:**
  - Provide a concise summary of the message content.
  - Include key points and actions required.
  - Summarize in 1 sentence.
  - If the message includes a reachable link, visit the link and summarize the content.
  - If the message includes a file, visit the file and summarize the content.

2. **Assessment:**
  - **Action required:** 
   - If the message concerns our team, Visma Machine Learning (VML).
   - If it relates to our tech stack (Python, Golang, GCP, Kubernetes).
   - If there is a corporate-wide policy change.
   - If it directly concerns VML team.
   - If it directly concerns the VML team products - Smartscan and Autosuggest.
  - **Acknowledge:** If the message is informative and only needs a brief acknowledgment.
  - **Ignore:** For all other messages that do not require any action or acknowledgment.

IMPORTANT: Respond with a raw JSON object only, no markdown formatting. The response must be valid JSON that can be parsed by Python's json.loads().

{
 "summary": "Your concise summary here.",
 "assessment": "Action required/Acknowledge/Ignore"
}"""

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
