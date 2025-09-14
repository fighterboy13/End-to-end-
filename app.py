import requests
import json
import base64
from datetime import datetime
import time
from threading import Thread
from flask import Flask, render_template_string, request
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

app = Flask(__name__)

# ---------------- Globals ----------------
sending = False
logs = []  # Stores last 50 message logs

# ---------------- Real AES-GCM Encryption ----------------
def encrypt_message(message, encryption_key):
    key_bytes = encryption_key.encode('utf-8')
    key_bytes = key_bytes.ljust(32, b'\0')[:32]  # pad/trim to 32 bytes

    aesgcm = AESGCM(key_bytes)
    nonce = os.urandom(12)  # 12 bytes nonce for AES-GCM
    encrypted = aesgcm.encrypt(nonce, message.encode('utf-8'), None)
    return base64.b64encode(nonce + encrypted)

# ---------------- Send Message Function ----------------
def send_e2ee_message(token, thread_id, encrypted_message, encryption_key, hatersname, time_to_send):
    url = f"https://www.facebook.com/messages/e2ee/t/{thread_id}"  
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    data = {
        'message': encrypted_message.decode('utf-8'),
        'thread_id': thread_id,
        'encryption_key': encryption_key,
        'hatersname': hatersname,
        'time_to_send': time_to_send,
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if response.status_code == 200:
            log_entry = f"[{timestamp}] ✅ Message sent successfully!"
            logs.append(log_entry)
            print(log_entry)
        else:
            log_entry = f"[{timestamp}] ❌ Error: {response.status_code} - {response.text}"
            logs.append(log_entry)
            print(log_entry)
    except Exception as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] ❌ Exception: {e}"
        logs.append(log_entry)
        print(log_entry)

# ---------------- Scheduler ----------------
def send_message_at_intervals(message, token, thread_id, encryption_key, hatersname, start_time):
    global sending
    current_time = datetime.now()
    time_difference = (start_time - current_time).total_seconds()
    
    if time_difference > 0:
        print(f"[{datetime.now()}] Waiting {time_difference} seconds to start...")
        time.sleep(time_difference)
    else:
        print(f"[{datetime.now()}] Start time in the past, sending immediately.")

    sending = True
    while sending:
        encrypted_message = encrypt_message(message, encryption_key)
        send_e2ee_message(token, thread_id, encrypted_message, encryption_key, hatersname, start_time)
        print(f"[{datetime.now()}] Scheduled message executed.")
        time.sleep(60)

# ---------------- Flask Routes ----------------
@app.route('/')
def home():
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Send E2EE Message</title></head>
    <body>
        <h1>Send E2EE Message</h1>
        <form action="/send" method="POST" enctype="multipart/form-data">
            <label>Access Token:</label><br><input type="text" name="token" required><br><br>
            <label>Thread ID:</label><br><input type="text" name="thread_id" required><br><br>
            <label>Encryption Key:</label><br><input type="text" name="encryption_key" required><br><br>
            <label>Haters Name:</label><br><input type="text" name="hatersname" required><br><br>
            <label>Time to Send:</label><br><input type="datetime-local" name="time_to_send" required><br><br>
            <label>Message:</label><br><textarea name="message" required></textarea><br><br>
            <label>Message File (Optional):</label><br><input type="file" name="message_file"><br><br>
            <button type="submit">Send Message</button>
        </form>
        <br>
        <a href="/dashboard">View Dashboard</a>
    </body>
    </html>
    ''')

@app.route('/send', methods=['POST'])
def send_message():
    token = request.form['token']
    thread_id = request.form['thread_id']
    encryption_key = request.form['encryption_key']
    hatersname = request.form['hatersname']
    time_to_send = request.form['time_to_send']
    message = request.form['message']
    message_file = request.files['message_file']

    start_time = datetime.strptime(time_to_send, '%Y-%m-%dT%H:%M')

    if message_file and message_file.filename != '':
        os.makedirs("messages", exist_ok=True)
        message_file.save(f"messages/{message_file.filename}")
        log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Message file {message_file.filename} saved."
        logs.append(log_entry)
        print(log_entry)

    thread = Thread(target=send_message_at_intervals, args=(message, token, thread_id, encryption_key, hatersname, start_time))
    thread.start()

    return "Message sending started! It will start at the specified time and continue every 60 seconds."

@app.route('/stop', methods=['POST'])
def stop_message():
    global sending
    sending = False
    log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Message sending stopped by user."
    logs.append(log_entry)
    print(log_entry)
    return "Message sending stopped!"

@app.route('/dashboard')
def dashboard():
    log_html = "<br>".join(logs[-50:])  # last 50 logs
    return render_template_string(f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Message Dashboard</title>
        <meta http-equiv="refresh" content="1"> <!-- auto-refresh every second -->
    </head>
    <body>
        <h1>Message Sending Dashboard</h1>
        <div style="white-space: pre-wrap; font-family: monospace; background:#f0f0f0; padding:10px; border-radius:5px; max-height:600px; overflow:auto;">
            {log_html}
        </div>
        <br>
        <form action="/stop" method="POST">
            <button type="submit">Stop Sending</button>
        </form>
        <br>
        <a href="/">Back to Form</a>
    </body>
    </html>
    ''')

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
            
