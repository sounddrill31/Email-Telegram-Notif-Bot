import asyncio
import aioimaplib
import email
from email.header import decode_header
from telegram import Bot
import re
import logging

# Add logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
EMAIL = "arealperson@gmail.com"
PASSWORD = "apppass"
TELEGRAM_BOT_TOKEN = "abot:realbot"
TELEGRAM_CHAT_ID = "@iitm_bs_es_info"
CHECK_INTERVAL = 600  # Check emails every 5 minutes

async def send_telegram_message(message):
    bot = Bot(TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='HTML')

def decode_email_subject(subject):
    decoded_subject, encoding = decode_header(subject)[0]
    if isinstance(decoded_subject, bytes):
        return decoded_subject.decode(encoding or 'utf-8')
    return decoded_subject

def parse_email_body(email_message):
    if email_message.is_multipart():
        for part in email_message.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode()
    else:
        return email_message.get_payload(decode=True).decode()

def format_telegram_message(subject, body):
    if "Content released" in subject:
        match = re.search(r'Week (\d+).+?(\w+(?:\s+\w+)?)\s*\n\nDear Learner,\s*\n\n(.+?)\s*\n\nWarm Regards', body, re.DOTALL)
        if match:
            week, course, content = match.groups()
            return (f"📚 <b>New Content Released</b>\n\n"
                    f"📅 Week {week}\n"
                    f"📘 Course: {course}\n\n"
                    f"{content}\n\n"
                    f"🔔 Don't forget to check the deadline!")
    
    elif "Live Session Details" in subject:
        match = re.search(r'Course: (.+?)\nGmeet Link: (.+?)\nDate: (.+?)\nTime: (.+)', body)
        if match:
            course, link, date, time = match.groups()
            return (f"🎥 <b>Live Session Scheduled</b>\n\n"
                    f"📘 Course: {course}\n"
                    f"📅 Date: {date}\n"
                    f"🕒 Time: {time}\n"
                    f"🔗 Link: {link}")
    
    elif "Assignment Deadline Reminder" in subject:
        match = re.search(r'Week (\d+).+?(\w+(?:\s+\w+)?)\s*\n\nDear Learner,\s*\n\n(.+?)\s*\n\nRegards', body, re.DOTALL)
        if match:
            week, course, content = match.groups()
            return (f"⏰ <b>Assignment Deadline Reminder</b>\n\n"
                    f"📅 Week {week}\n"
                    f"📘 Course: {course}\n\n"
                    f"{content}")
    
    elif "Revision sessions" in subject:
        sessions = re.findall(r'(ES_.+?)\nGoogle Meet: (.+?)\nDate: (.+?)\nTime:(.+?)(?:\n|$)', body)
        if sessions:
            message = "📚 <b>Revision Sessions Scheduled</b>\n\n"
            for session, link, date, time in sessions:
                message += (f"🔖 {session}\n"
                            f"📅 Date: {date}\n"
                            f"🕒 Time: {time}\n"
                            f"🔗 Link: {link}\n\n")
            return message
    
    # If no specific format matches, return a generic formatted message
    return f"📬 <b>{subject}</b>\n\n{body[:200]}..."

async def check_emails():
    while True:
        imap_client = None
        try:
            logging.info("Connecting to IMAP server...")
            imap_client = aioimaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            await imap_client.wait_hello_from_server()
            
            logging.info("Attempting to log in...")
            response = await imap_client.login(EMAIL, PASSWORD)
            if response.result != 'OK':
                raise Exception(f"Login failed: {response}")
            logging.info("Successfully logged in")
            
            logging.info("Selecting INBOX...")
            response = await imap_client.select('INBOX')
            if response.result != 'OK':
                raise Exception(f"Failed to select INBOX: {response}")
            logging.info("INBOX selected successfully")

            logging.info("Searching for emails...")
            _, message_numbers = await imap_client.search('(FROM "*-announce@study.iitm.ac.in" UNSEEN)')
            for num in message_numbers[0].split():
                logging.info(f"Fetching email {num}...")
                _, msg_data = await imap_client.fetch(num, '(RFC822)')
                
                if msg_data[0] is not None and isinstance(msg_data[0], tuple):
                    email_body = msg_data[0][1]
                    if isinstance(email_body, bytes):
                        email_message = email.message_from_bytes(email_body)
                    else:
                        logging.warning(f"Unexpected email body type: {type(email_body)}")
                        continue

                    subject = decode_email_subject(email_message['subject'])
                    body = parse_email_body(email_message)
                    
                    formatted_message = format_telegram_message(subject, body)
                    await send_telegram_message(formatted_message)
                    logging.info(f"Processed and sent message: {subject}")
                else:
                    logging.warning(f"Unexpected message data structure for email {num}")

            logging.info("Finished processing emails")

        except aioimaplib.Abort as e:
            logging.error(f"IMAP Abort error: {str(e)}")
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            logging.exception("Exception details:")
        finally:
            if imap_client:
                try:
                    logging.info("Logging out from IMAP server...")
                    await imap_client.logout()
                    logging.info("Logged out successfully")
                except Exception as e:
                    logging.error(f"Error during logout: {str(e)}")
        
        logging.info(f"Waiting {CHECK_INTERVAL} seconds before next check")
        await asyncio.sleep(CHECK_INTERVAL)

async def main():
    while True:
        try:
            await check_emails()
        except Exception as e:
            logging.error(f"Main loop error: {str(e)}")
            await asyncio.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    asyncio.run(main())