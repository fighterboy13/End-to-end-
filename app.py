import requests
import json
import base64
from datetime import datetime
from threading import Thread
from flask import Flask, render_template_string, request
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import time

app = Flask(__name__)

# ---------------- Globals ----------------
sending = False
logs = []

# ---------------- Load Encryption Key ----------------
def load_encryption_key():
    try:
        with open("encryption_keys/plan.txt", "r") as f:
            key = f.read().strip()
            if len(key) == 0:
                raise ValueError("plan.txt is empty")
            return key
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to load encryption key: {e}")
        return None

# ---------------- Load messages from TXT ----------------
def load_messages_list():
    try:
        with open("messages_list.txt", "r") as f:
            lines = [line.strip() for line in f if line.strip()]
            if not lines:
                raise ValueError("messages_list.txt is empty")
            return lines
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to load messages list: {e}")
        return []

# ---------------- AES-GCM Encryption ----------------
def encrypt_message(message, encryption_key):
    key_bytes = encryption_key.encode('utf-8')
    key_bytes = key_bytes.ljust(32, b'\0')[:32]
    aesgcm = AESGCM(key_bytes)
    nonce = os.urandom(12)
    encrypted = aesgcm.encrypt(nonce, message.encode('utf-8'), None)
    return base64.b64encode(nonce + encrypted)

# ---------------- Send message with retry ----------------
def send_e2ee_message(token, thread_id, encrypted_message, hatersname):
    url = f"https://www.facebook.com/messages/e2ee/t/{thread_id}"  
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Origin': 'https://www.facebook.com',
        'Referer': 'https://www.facebook.com/messages'
    }
    data = {
        'message': encrypted_message.decode('utf-8'),
        'thread_id': thread_id,
        'hatersname': hatersname,
    }

    max_attempts = 3
    for attempt in range(1, max_attempts+1):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if response.status_code == 200:
                log_entry = f"[{timestamp}] ✅ Message sent successfully!"
                logs.append(log_entry)
                print(log_entry)
                break
            else:
                log_entry = f"[{timestamp}] ❌ Error: {response.status_code} - {response.text} (Attempt {attempt})"
                logs.append(log_entry)
                print(log_entry)
                time.sleep(2)
        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] ❌ Exception: {e} (Attempt {attempt})"
            logs.append(log_entry)
            print(log_entry)
            time.sleep(2)

# ---------------- Multi-message sender ----------------
def send_multiple_messages(token, thread_id, hatersname):
    global sending
    sending = True
    encryption_key = load_encryption_key()
    if not encryption_key:
        logs.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ Encryption key not loaded. Aborting.")
        return

    messages = load_messages_list()
    if not messages:
        logs.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ Messages list empty. Aborting.")
        return

    log_start = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduler started - sending {len(messages)} messages."
    logs.append(log_start)
    print(log_start)

    for msg in messages:
        if not sending:
            logs.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sending stopped by user.")
            break
        encrypted_message = encrypt_message(msg, encryption_key)
        send_e2ee_message(token, thread_id, encrypted_message, hatersname)

# ---------------- Flask Routes ----------------
@app.route('/')
def home():
    return render_template_string('''
    <h1>Send Multiple E2EE Messages (Immediate)</h1>
    <form action="/send" method="POST" enctype="multipart/form-data">
        <label>Access Token:</label><br><input type="text" name="token" required><br><br>
        <label>Thread ID:</label><br><input type="text" name="thread_id" required><br><br>
        <label>Haters Name:</label><br><input type="text" name="hatersname" required><br><br>
        <label>Optional Message File Upload:</label><br><input type="file" name="message_file"><br><br>
        <button type="submit">Send All Messages</button>
    </form>
    <br>
    <a href="/dashboard">View Dashboard</a>
    ''')

@app.route('/send', methods=['POST'])
def send_message():
    token = request.form['token']
    thread_id = request.form['thread_id']
    hatersname = request.form['hatersname']
    message_file = request.files['message_file']

    # Optional file save
    if message_file and message_file.filename != '':
        os.makedirs("messages", exist_ok=True)
        message_file.save(f"messages/{message_file.filename}")
        log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Message file {message_file.filename} saved."
        logs.append(log_entry)
        print(log_entry)

    thread = Thread(target=send_multiple_messages, args=(token, thread_id, hatersname))
    thread.start()

    return f"Started sending multiple messages immediately! Check Dashboard for logs."

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
    log_html = "<br>".join(logs[-50:])
    return render_template_string(f'''
    <h1>Message Dashboard</h1>
    <div style="white-space: pre-wrap; font-family: monospace; background:#f0f0f0; padding:10px; border-radius:5px; max-height:600px; overflow:auto;">
        {log_html}
    </div>
    <br>
    <form action="/stop" method="POST">
        <button type="submit">Stop Sending</button>
    </form>
    <br>
    <a href="/">Back to Form</a>
    <meta http-equiv="refresh" content="1">
    ''')

if __name__ == '__main__':
    os.makedirs("encryption_keys", exist_ok=True)
    app.run(debug=True, host="0.0.0.0", port=5000)
    
