from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import dateparser
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from groq import Groq
import json

# Load .env
load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_whatsapp_number = "whatsapp:+14155238886"

twilio_client = Client(account_sid, auth_token)
scheduler = BackgroundScheduler()
scheduler.start()

app = FastAPI()

@app.get("/")
async def root():
    return "I am ALIVE!"

@app.post("/whatsapp", response_class=PlainTextResponse)
async def whatsapp_bot(request: Request):
    # Twilio sends form-encoded POST
    form = await request.form()
    msg = form.get("Body")
    print(f"this is what Amin sent: {msg}")
    sender = form.get("From")

    # parsed_date = dateparser.parse(msg, settings={'PREFER_DATES_FROM': 'future'})
    import re

    # Extract time-like or date-like phrases
    # cleaned_msg = re.sub(r"(?i)remind me to|remind me|about|to", "", msg).strip()
    # parsed_date = dateparser.parse(cleaned_msg, settings={'PREFER_DATES_FROM': 'future'})
    task, datetime_str = parse_with_llm(msg)
    parsed_date = dateparser.parse(datetime_str, settings={'PREFER_DATES_FROM': 'future'})

    if parsed_date:
        reminder_time = parsed_date - timedelta(minutes=1)
        print(reminder_time)
        scheduler.add_job(send_reminder, 'date', run_date=reminder_time, args=[sender, msg])
        reply_text = f"✅ Got it! I’ll remind you 1 minute before {parsed_date.strftime('%I:%M %p, %d %B %Y')}."
    else:
        reply_text = ("❌ Sorry, I couldn’t understand that.\n"
                      "Try something like:\n"
                      "'Remind me to take medicine at 9 PM today'")

    # Return Twilio-compatible XML
    response = MessagingResponse()
    response.message(reply_text)
    return str(response)

def send_reminder(to, task):
    twilio_client.messages.create(
        body=f"⏰ Reminder: {task}",
        from_=twilio_whatsapp_number,
        to=to
    )

def llm_api_call(prompt: str) -> str:
    """Calls the Groq LLM and returns the raw text response."""
    # Use the Groq client to create a chat completion. The Groq SDK exposes a
    # `chat.create` method on the client.chat object. We try a couple of
    # extraction patterns to be resilient to minor SDK response-shape
    # differences.
    # Some versions of the Groq SDK expose `chat.create`, others expose
    # `chat.completions.create`. Try both to be resilient to SDK changes.
    try:
        completion = groq_client.chat.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
    except AttributeError:
        # Try the older/newer alternate method name
        try:
            completion = groq_client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
        except Exception as e:
            return f"LLM call failed: {e}"

    # Extract text from known possible response shapes
    try:
        return completion.choices[0].message.content
    except Exception:
        try:
            return completion.choices[0].message["content"]
        except Exception:
            # Fallback: stringified response
            return str(completion)


def parse_with_llm(message: str):
    """Uses the LLM to extract task and datetime."""
    prompt = f"""
    Extract the task and the exact date/time from this reminder request:
    "{message}"
    Respond strictly in JSON format with keys 'task' and 'datetime'.
    Example:
    user prompt: "Remind me to call mom tomorrow at 9 PM"
    output(ONLY JSON,NO EXTRA TEXT):
    {{
        "task": "call your mom",
        "datetime": "tomorrow at 9 PM"
    }}
    """

    response = llm_api_call(prompt)
    print(response)
    # Handle LLM response safely
    try:
        data = json.loads(response)
        print(data)
        return data["task"], data["datetime"]
    except json.JSONDecodeError:
        # If LLM doesn’t return valid JSON, handle gracefully
        print("Failed to parse LLM response as JSON.")
        return message, None

# def parse_with_llm(message):
#     prompt = f"""
#     Extract the task and the exact date/time from this reminder request:
#     "{message}"
#     Respond in JSON with 'task' and 'datetime'.
#     """
#     # pseudo-code: call Grok/OpenAI API
#     response = llm_api_call(prompt)
#     data = json.loads(response)
#     return data["task"], data["datetime"]    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)