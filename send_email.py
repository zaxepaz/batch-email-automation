import os
import sys
import uuid
from tkinter import Tk, Label, Entry, Button, Frame, filedialog, Text, Scrollbar, END, messagebox, IntVar, Checkbutton
from PIL import Image, ImageTk
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64
import re
import time
import random
from tkinter import messagebox

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_gmail_service():
    creds = None
    credentials_path = resource_path("credentials.json")
    token_path = os.path.join(os.path.expanduser("~"), ".my_email_app_token.json")
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as f:
            f.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def send_email(to_email, subject, body_html, attachments=None, inline_images=None, cc=None, bcc=None):
    service = get_gmail_service()
    msg = MIMEMultipart('related')
    msg['to'] = to_email
    msg['subject'] = subject
    if cc: msg['cc'] = cc
    if bcc: msg['bcc'] = bcc

    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(body_html, 'html'))
    msg.attach(alt)

    if inline_images:
        for cid, img_path in inline_images.items():
            with open(img_path, 'rb') as f:
                img_data = f.read()
            img = MIMEImage(img_data)
            img.add_header('Content-ID', f'<{cid}>')
            img.add_header('Content-Disposition', 'inline', filename=os.path.basename(img_path))
            msg.attach(img)

    if attachments:
        for file_path in attachments:
            part = MIMEBase('application', 'octet-stream')
            with open(file_path, 'rb') as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_path)}"')
            msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()

class EmailRow:
    def __init__(self, master, row, delete_callback):
        self.master = master
        self.row = row
        self.delete_callback = delete_callback

        self.email_entry = Entry(master, width=25)
        self.email_entry.grid(row=row, column=0)
        self.name_entry = Entry(master, width=15)
        self.name_entry.grid(row=row, column=1)
        self.subject_entry = Entry(master, width=25)
        self.subject_entry.grid(row=row, column=2)

        self.attachment_path = None
        self.attachment_btn = Button(master, text="Add", command=self.add_attachment)
        self.attachment_btn.grid(row=row, column=3)
        self.attachment_label = Label(master, text="", width=15, anchor="w")
        self.attachment_label.grid(row=row, column=4)
        self.attachment_del_btn = Button(master, text="Delete", command=self.delete_attachment)
        self.attachment_del_btn.grid(row=row, column=5)

        self.cc_entry = Entry(master, width=20)
        self.cc_entry.grid(row=row, column=6)
        self.bcc_entry = Entry(master, width=20)
        self.bcc_entry.grid(row=row, column=7)

        self.delete_row_btn = Button(master, text="Delete Recipient", command=self.delete_row)
        self.delete_row_btn.grid(row=row, column=8)

    def add_attachment(self):
        file = filedialog.askopenfilename()
        if file:
            self.attachment_path = file
            self.attachment_label.config(text=os.path.basename(file))

    def delete_attachment(self):
        self.attachment_path = None
        self.attachment_label.config(text="")

    def delete_row(self):
        for widget in [self.email_entry, self.name_entry, self.subject_entry, self.attachment_btn,
                       self.attachment_label, self.attachment_del_btn, self.cc_entry, self.bcc_entry,
                       self.delete_row_btn]:
            widget.grid_forget()
            widget.destroy()
        self.delete_callback(self)

    def get_data(self):
        return {
            "email": self.email_entry.get().strip(),
            "name": self.name_entry.get().strip(),
            "subject": self.subject_entry.get().strip(),
            "attachment": self.attachment_path,
            "cc": self.cc_entry.get().strip(),
            "bcc": self.bcc_entry.get().strip()
        }

class EmailApp:
    def __init__(self):
        self.root = Tk()
        self.root.title("Per-Recipient Email Sender with Inline Images")
        self.rows = []
        self.inline_images = {}  # cid -> file path
        self.inline_image_objects = {}  # keep Tk images

        headers = ["Email", "Name", "Subject", "Attachment", "Label", "Del Att.", "CC", "BCC", "Del Recipient"]
        for i, h in enumerate(headers):
            Label(self.root, text=h).grid(row=0, column=i)

        self.add_row_button_row = 1
        self.add_row()

        Button(self.root, text="Add Recipient", command=self.add_row).grid(row=100, column=0, pady=10, sticky="w")

        self.use_global_ccbcc = IntVar()
        Checkbutton(self.root, text="Use same CC/BCC for all", variable=self.use_global_ccbcc).grid(row=101, column=0, sticky="w")
        Label(self.root, text="Global CC:").grid(row=102, column=0, sticky="w")
        self.global_cc = Entry(self.root, width=50)
        self.global_cc.grid(row=102, column=1, columnspan=3, sticky="w")
        Label(self.root, text="Global BCC:").grid(row=103, column=0, sticky="w")
        self.global_bcc = Entry(self.root, width=50)
        self.global_bcc.grid(row=103, column=1, columnspan=3, sticky="w")

        Label(self.root, text="Body:").grid(row=104, column=0, sticky="nw")
        body_frame = Frame(self.root)
        body_frame.grid(row=105, column=0, columnspan=9)
        scrollbar = Scrollbar(body_frame)
        scrollbar.pack(side="right", fill="y")
        self.body_text = Text(body_frame, width=120, height=20, yscrollcommand=scrollbar.set, wrap="word")
        self.body_text.pack(side="left", fill="both")
        scrollbar.config(command=self.body_text.yview)

        Button(self.root, text="Add Inline Image", command=self.add_inline_image).grid(row=106, column=0, pady=5, sticky="w")
        Button(self.root, text="Delete Last Inline Image", command=self.delete_last_inline_image).grid(row=106, column=1, pady=5, sticky="w")

        Button(self.root, text="Send Emails", command=self.send_all).grid(row=107, column=0, columnspan=9, pady=10)

        self.root.mainloop()

    def add_row(self):
        row_num = len(self.rows) + 2
        row = EmailRow(self.root, row_num, delete_callback=self.remove_row)
        self.rows.append(row)

    def remove_row(self, row):
        self.rows.remove(row)

    def add_inline_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files","*.png;*.jpg;*.jpeg;*.gif")])
        if not file_path:
            return
        cid = str(uuid.uuid4())
        img = Image.open(file_path)
        max_width = 400
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((int(img.width*ratio), int(img.height*ratio)))
        img_tk = ImageTk.PhotoImage(img)
        self.inline_image_objects[cid] = img_tk
        self.inline_images[cid] = file_path

        self.body_text.image_create("insert", image=img_tk)
        self.body_text.insert("insert", f"[IMAGE:{cid}]")

    def delete_last_inline_image(self):
        if not self.inline_images:
            messagebox.showinfo("Info", "No inline images to delete.")
            return
        last_cid = list(self.inline_images.keys())[-1]
        del self.inline_images[last_cid]
        del self.inline_image_objects[last_cid]
        messagebox.showinfo("Info", f"Deleted last inline image: {last_cid}")

    def send_all(self):
        body_text_content = self.body_text.get("1.0", END)
        global_cc = self.global_cc.get().strip() if self.use_global_ccbcc.get() else None
        global_bcc = self.global_bcc.get().strip() if self.use_global_ccbcc.get() else None

        total_emails = len([row for row in self.rows if row.get_data()["email"].strip() != ""])
        if total_emails == 0:
            messagebox.showwarning("Warning", "No recipients to send emails to!")
            return

        popup = Tk()
        popup.title("Sending Emails")
        Label(popup, text="Email Sending Progress", font=("Arial", 14, "bold")).pack(pady=10)
        progress_label = Label(popup, text="", font=("Arial", 12))
        progress_label.pack(pady=5)
        countdown_label = Label(popup, text="", font=("Arial", 12), fg="blue")
        countdown_label.pack(pady=5)
        popup.update()

        sent_count = 0

        for row in self.rows:
            data = row.get_data()
            email = data["email"]
            if not email:
                continue

            personalized_body = (
                f'<div style="font-family: serif;"><b>Dear {data["name"]},</b><br>{body_text_content}</div>'
                if data["name"] else f'<div style="font-family: serif;">{body_text_content}</div>'
            )
            
            body_html = ""
            lines = personalized_body.splitlines(True)
            for line in lines:
                match = re.findall(r"\[IMAGE:(.+?)\]", line)
                if match:
                    segments = re.split(r"(\[IMAGE:.+?\])", line)
                    for seg in segments:
                        m = re.match(r"\[IMAGE:(.+?)\]", seg)
                        if m:
                            cid = m.group(1)
                            body_html += f'<img src="cid:{cid}" style="max-width:600px; width:100%; height:auto;"><br>'
                        else:
                            body_html += seg.replace("\n", "<br>")
                else:
                    body_html += line.replace("\n", "<br>")

            subject = data["subject"] if data["subject"] else "No Subject"
            attachments = [data["attachment"]] if data["attachment"] else None
            cc = global_cc if global_cc else (data["cc"] if data["cc"] else None)
            bcc = global_bcc if global_bcc else (data["bcc"] if data["bcc"] else None)

            send_email(email, subject, body_html, attachments, self.inline_images, cc, bcc)
            sent_count += 1

            interval = random.randint(180, 300)

            pending = total_emails - sent_count
            progress_label.config(text=f"Sent {sent_count}/{total_emails}\nPending: {pending}")
            popup.update()

            for remaining in range(interval, 0, -1):
                minutes, seconds = divmod(remaining, 60)
                countdown_label.config(text=f"Next email in: {minutes:02d}:{seconds:02d}")
                popup.update()
                time.sleep(1)

        progress_label.config(text=f"All {total_emails} emails sent!")
        countdown_label.config(text="")
        Button(popup, text="Close", command=popup.destroy).pack(pady=10)
        popup.mainloop()


if __name__ == "__main__":
    EmailApp()
