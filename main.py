import os.path
import os

import base64

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from bs4 import BeautifulSoup

import openai
from dotenv import load_dotenv

import re

import requests

import winsound


load_dotenv()

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


def get_gmail_service():
    """Function to initiate the service for google gmail api"""

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        service = build("gmail", "v1", credentials=creds)

        return service
    else:
        raise FileNotFoundError(
            "Token.json doesnot exit, Run first \
                                ` python validate_email.py `"
        )


def get_unread_emails(service):
    query = "is:unread is:inbox after:2023/11/23 before:2023/11/27 category:primary"
    response = service.users().messages().list(userId="me", q=query).execute()
    messages = []

    if "messages" in response:
        messages.extend(response["messages"])

    while "nextPageToken" in response:
        page_token = response["nextPageToken"]
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, pageToken=page_token)
            .execute()
        )

        if "messages" in response:
            messages.extend(response["messages"])

    return messages


def get_email_data(msg_id):
    """Function to extract information form id"""

    msg = (
        service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    )

    payload = msg["payload"]
    headers = payload["headers"]
    email_data = {"id": msg_id}

    for header in headers:
        name = header["name"]
        value = header["value"]
        if name == "From":
            email_data["from"] = value
        if name == "Date":
            email_data["date"] = value
        if name == "Subject":
            email_data["subject"] = value

    if "parts" in payload:
        parts = payload["parts"]
        data = None
        for part in parts:
            if part["mimeType"] == "text/plain":
                data = part["body"]["data"]
            elif part["mimeType"] == "text/html":
                data = part["body"]["data"]

        if data is not None:
            text = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("UTF-8")
            soup = BeautifulSoup(text, "html.parser")
            clean_text = soup.get_text()
            email_data["text"] = clean_text
        else:
            data = payload["body"]["data"]
            text = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("UTF-8")
            soup = BeautifulSoup(text, "html.parser")
            clean_text = soup.get_text()
            email_data["text"] = clean_text

    else:
        data = payload["body"]["data"]
        text = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("UTF-8")
        soup = BeautifulSoup(text, "html.parser")
        email_data["text"] = soup.get_text()

    return email_data


def generate_summary(txt_email):
    """Uses openai to generate summary of the email"""

    _DEFAULT_PROMPT_ = "Assume you are a friendly assistant. You have just checked to see if there are any \
    new noteworthy emails to summarize. If No emails are available, so let the user know that there are no new\
    emails to report and provide reassurance that you're keeping an eye on their inbox.\
    Ensure that your response works best when spoken and maintain a tone that demonstrates emotional intelligence.\
    also only summarize the email dont ask for further assistance."

    openai.api_key = os.environ["OPENAPI_KEY"]

    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": (_DEFAULT_PROMPT_)},
            {
                "role": "user",
                "content": (
                    "Create summary of "
                    + txt_email
                    + "in less than 20 words without bullet point."
                ),
            },
        ],
        temperature=0.5,
    )

    return response.choices[0].message.content.strip()


def mark_email_read(service, email_id):
    """Marks the email read"""

    try:
        service.users().messages().modify(
            userId="me", id=email_id, body={"removeLabelIds": ["UNREAD", "INBOX"]}
        ).execute()

    except Exception as e:
        print(f"Issue occured due to {e}")


def text_to_speech(text):
    """Convert text to speech using elevenlab"""
    try:
        import requests
    except ModuleNotFoundError:
        raise ModuleNotFoundError(
            """Request doesnot seems to be installed,\
            `pip install requests`"""
        )

    CHUNK_SIZE = 1024
    url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": "Your_eleven_lab_api",
    }

    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
    }

    response = requests.post(url, json=data, headers=headers)
    with open("summarized_result.mp3", "wb") as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)


if __name__ == "__main__":
    service = get_gmail_service()
    unread_emails = get_unread_emails(service)

    if len(unread_emails) == 0:
        message = """I'm sorry Ashish, but I couldn't find any new emails to summarize for you at the moment.\
          Rest assured, I'll continue to keep an eye on your inbox and let you know as soon as there are \
          any noteworthy updates."""
    else:
        message = f"Hellow, ashish you got {len(unread_emails)} unread email. Let me summarize it for you."

    for num_unread in range(len(unread_emails)):
        email_id = unread_emails[num_unread]["id"]
        email_data = get_email_data(email_id)
        sent_by = re.sub(r"<[^>]*>", "", email_data["from"])
        summarized_email = generate_summary(email_data["text"])
        message = (
            message + f"\n Email {num_unread} by {sent_by}\n" + summarized_email + "\n"
        )

        mark_email_read(service, email_id)

    print(message)
    text_to_speech(message)
    # print(email_data)

# print(unread_emails)
