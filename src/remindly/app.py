from fastapi import FastAPI, Request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import dateparser
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import timedelta
import os
from dotenv import load_dotenv
from groq import Groq
import phonenumbers
from phonenumbers import timezone as phonenumbers_timezone
import json 
import re

# Load .env
load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
number=os.getenv("NUMBER")
client = Client(account_sid, auth_token)
twilio_whatsapp_number = f"whatsapp:{os.getenv('TWILIO_WHATSAPP_NUMBER')}"

twilio_client = Client(account_sid, auth_token)
scheduler = BackgroundScheduler()
scheduler.start()

app = FastAPI()

# @app.get("/make_call")
def make_call(task):
    call = client.calls.create(
    twiml=f'''<Response>
      <Say voice="alice">{task}</Say>
    </Response>''',
    from_="+19785816814",
    to=number,
)

    print(call.sid)

@app.get("/")
async def root():
    return "I am ALIVE!"

@app.post("/whatsapp")
async def whatsapp_bot(request: Request):
    # Twilio sends form-encoded POST
    form = await request.form()
    msg = form.get("Body")
    print(f"User msg: {msg}")
    sender = form.get("From")
    task, datetime_str, call_intent, reply = parse_with_llm(msg)
    print(f"call_intent: {call_intent}")
    print(f"Extracted task: {task}, datetime string: {datetime_str}")
    user_tz = get_timezone_name_from_number(sender)
    print(f"Detected timezone for {sender}: {user_tz}")
    parsed_date = dateparser.parse(datetime_str, settings={
        'PREFER_DATES_FROM': 'future',
        'TIMEZONE': user_tz,                # ✅ interpret input in user’s zone
        'RETURN_AS_TIMEZONE_AWARE': True,   # ✅ attach tzinfo
        'TO_TIMEZONE': user_tz,             
    })

    if parsed_date:
        reminder_time = parsed_date - timedelta(minutes=1)
        print(reminder_time)
        if call_intent:
            scheduler.add_job(make_call, 'date', run_date=reminder_time, args=[task])
            reply_text = f"✅ {reply} {parsed_date.strftime('%I:%M %p, %d %B %Y')}."
        else:
            scheduler.add_job(send_reminder, 'date', run_date=reminder_time, args=[sender, task])
            reply_text = f"✅ {reply} {parsed_date.strftime('%I:%M %p, %d %B %Y')}."
    else:
        reply_text = ("❌ Sorry, I couldn’t understand that.\n"
                      "Try something like:\n"
                      "'Remind me to take medicine at 9 PM today'")

    # Return Twilio-compatible XML
    response = MessagingResponse()
    print(f"this is replytext {reply_text}")
    print(dir(response))
    response.message(reply_text)
    twilio_client.messages.create(
        body=reply_text, 
        from_=twilio_whatsapp_number,
        to=sender
    )
    
def get_time_zone():
    from datetime import datetime
    import zoneinfo
    print("Getting local timezone...")

    # Get local time and timezone
    local_time = datetime.now().astimezone()
    return local_time.tzinfo

def send_reminder(to, task):
    twilio_client.messages.create(
        body=f"⏰ Reminder: {task}",
        from_=twilio_whatsapp_number,
        to=to
    )
    

def get_timezone_name_from_number(phone_number: str) -> str:
    """
    Returns the IANA timezone name (e.g., 'Asia/Kolkata', 'America/New_York')
    inferred from a phone number.

    Falls back to 'UTC' if no timezone can be determined.
    """
    try:
        # Parse number (Twilio numbers often come like 'whatsapp:+919876543210')
        if phone_number.startswith("whatsapp:"):
            phone_number = phone_number.replace("whatsapp:", "")

        parsed_number = phonenumbers.parse(phone_number, None)
        timezones = phonenumbers_timezone.time_zones_for_number(parsed_number)

        if timezones:
            print(f"Detected timezones for {phone_number}: {timezones}")
            return timezones[0]  # Usually one timezone is returned, sometimes more

    except Exception as e:
        print(f"⚠️ Error determining timezone for {phone_number}: {e}")

    # Fallback
    return "UTC"



# def get_the_time_acc_to_country_code(country_code):
#     """Returns the current time in a given country code."""
#     # Map country code to timezones
#     try:
#         timezones = phonenumbers_timezone.time_zones_for_number(parse(country_code, None))
#         if timezones:
#             tz = pytz.timezone(timezones[0])
#             country_time = datetime.now(tz)
#             print(f"Current time in {country_code} is {country_time}")
#             return country_time
#         else:
#             print(f"No timezone found for country code {country_code}, defaulting to UTC")
#             return "UTC"
#     except Exception as e:
#         print(f"Error getting timezone for country code {country_code}: {e}")
#         return "UTC"
    

def llm_api_call(prompt: str) -> str:
    """Calls the Groq LLM and returns the raw text response."""
    try:
        completion = groq_client.chat.completions.create(
            temperature=0.7,
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
        )
    except AttributeError:
        # Backup call in case of SDK version mismatch
        try:
            completion = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            return json.dumps({"error": f"LLM call failed: {e}"})

    # Extract text safely
    try:
        return completion.choices[0].message.content.strip()
    except Exception:
        try:
            return completion.choices[0].message["content"].strip()
        except Exception:
            return str(completion)


def extract_json_from_text(text: str) -> dict:
    """
    Attempts to extract and clean a JSON object from a text string.
    Returns None if no valid JSON found.
    """
    # Use regex to find JSON-like block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    json_str = match.group(0)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Try to auto-repair common formatting issues
        json_str = re.sub(r"(\w+):", r'"\1":', json_str)  # unquoted keys
        json_str = json_str.replace("'", '"')  # single to double quotes
        try:
            return json.loads(json_str)
        except Exception:
            return None


def parse_with_llm(message: str):
    """Uses the LLM to extract task and datetime in consistent JSON."""
    prompt = f"""
You are a MULTILINGUAL strict JSON generator.

Extract the task(and reword it in the SAME LANGUAGE to be a bit more friendly and descriptive and in the same tense as used in the task) and datetime from this reminder request, 
and identify if it includes a PHONE CALL request. AND also include "reply" key that has the TRANSLATED verion of "Got it! I will remind you 1 minute before".

Rules:
- Respond ONLY with a JSON object.
- Keys: "task", "datetime", "call_intent"
- task key must be in the SAME LANGUAGE as the input message, use the same tense as used in the task.
- datetime key must be in ENGLISH LANGUAGE ONLY.
- reply key must be in the SAME LANGUAGE as the input message.
- No explanation, no markdown, no text outside JSON.    

Example 1:
Input: "Remind me to text mom tomorrow at 9 PM"
Output:
{{
  "task": "you have to text your mom",
  "datetime": "tomorrow at 9 PM",
  "call_intent": false,
  "reply": "Got it! I will remind you 1 minute before"
}}

Example 2:
Input: "Set a call reminder to buy groceries in 2 hours"
Output:
{{
  "task": "you have to buy groceries",
  "datetime": "in 2 hours",
  "call_intent": true,
  "reply": "Got it! I will remind you 1 minute before"
}}
Example 3:
Input: "bus tickets book karna hai 2 minute mein, yaad dilao"
Output:
{{
  "task": "tumhe bus tickets book karna hai",
  "datetime": "in 2 minutes",
  "call_intent": false,
  "reply": "Thik hai! Main aapko 1 minute pehle yaad dilaoonga"
}}

Now process:
"{message}"
"""

    response = llm_api_call(prompt)
    print(f"🔹 Raw LLM response:\n{response}\n")

    data = extract_json_from_text(response)
    if data and all(k in data for k in ["task", "datetime", "call_intent"]):
        return data["task"], data["datetime"], data["call_intent"], data["reply"]

    print("⚠️ Failed to parse valid JSON. Returning fallback.")
    return message, None, False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)