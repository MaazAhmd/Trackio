import os
from functools import wraps

from dotenv import load_dotenv
from flask import redirect, url_for, flash
from flask_login import current_user, login_required
import mailtrap as mt

load_dotenv()

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def sendEmail(sender, message, project):
    mail = mt.Mail(
        sender=mt.Address(email="trackio@demomailtrap.com", name="Trackio"),
        to=[mt.Address(email="maazkhanahmad1@gmail.com")],
        subject=f"{sender} via Trackio",
        html=f"""
                    <html>
                    <body>
                        <h2>Payment Request</h2>
                        <p><strong>{sender}</strong> has sent a message regarding the project <strong>{project}</strong>.</p>
                        <p><strong>Message:</strong></p>
                        <p>{message}</p>
                        <p>Thank you!</p>
                    </body>
                    </html>
                """,
        text=f"{sender} has requested a payment from the project {project}. Message: {message}",
    )

    # create client and send
    client = mt.MailtrapClient(token=os.getenv("MAILTRAP_API_TOKEN"))
    client.send(mail)
