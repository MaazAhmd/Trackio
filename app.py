import random
from datetime import datetime, timedelta

import requests
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect

from helping_functions import sendEmail, otpEmail
from time_tracking import time_tracking
from time_entries import time_entries
from clients import clients_blueprint
from projects import projects_blueprint
from payments import payments
from config import Config
from consultants import consultants_blueprint
from communication_time import communication_times_blueprint
from models import User, db, Consultant, Consultant, Project, cache
from flask import request, flash
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, current_user, login_required, LoginManager, login_manager

app = Flask(__name__, static_folder='assets')
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)

cache.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

app.config["SESSION_COOKIE_SAMESITE"] = "strict"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["REMEMBER_COOKIE_SAMESITE"] = "strict"
app.config["REMEMBER_COOKIE_SECURE"] = True

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def is_active(url):
    return 'active' if url in request.path else ''


def is_activeSVG(url):
    return 'invert' if url in request.path else ''


app.jinja_env.globals['is_active'] = is_active
app.jinja_env.globals['is_activeSVG'] = is_active

app.register_blueprint(clients_blueprint, url_prefix='/clients')
app.register_blueprint(consultants_blueprint, url_prefix='/consultants')
app.register_blueprint(projects_blueprint, url_prefix='/projects')
app.register_blueprint(time_tracking, url_prefix='/')
app.register_blueprint(time_entries, url_prefix='/')
app.register_blueprint(payments, url_prefix='/payments')
app.register_blueprint(communication_times_blueprint, url_prefix='/communication_times')


@app.route('/')
def index():
    return redirect(url_for('time_tracking.track_time'))


@app.route('/create-password', methods=['GET', 'POST'])
def create_password():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))

    if request.method == 'POST':
        password = request.form.get('password')
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        session.pop('username', None)
        flash('Password created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('create-password.html')


def generate_otp():
    return random.randint(100000, 999999)  # 6-digit OTP

@app.route('/two-step-verification', methods=['GET', 'POST'])
def twoFactorAuthentication():
    username = session.get('username')
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not username or not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        entered_otp = request.form.get('code')
        stored_otp = session.get('otp')
        otp_expiry = session.get('otp_expiry')

        # Check if the OTP is still valid
        # if datetime.now() > otp_expiry:
        #     flash('OTP has expired. Please request a new one.')
        #     return redirect(url_for('twoFactorAuthentication'))

        # OTP SUCCESS:
        if entered_otp == str(stored_otp):
            session.pop('otp', None)
            session.pop('otp_expiry', None)

            flash('Two-factor authentication successful!')
            user.wrong_login_tries = 0
            db.session.commit()
            login_user(user)
            return redirect(url_for('index'))

        else:
            flash('Incorrect OTP. Please try again.')
            return redirect(url_for('twoFactorAuthentication'))

    else:
        otp = generate_otp()
        otp_expiry = datetime.now() + timedelta(minutes=2)  # OTP valid for 5 minutes

        session['otp'] = otp
        session['otp_expiry'] = otp_expiry

        otpEmail(username, otp)

        flash('An OTP has been sent to your email.')
        return render_template('two-factor-auth.html')  # Render the OTP input form


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        print(f"Received POST with username: {username}, password: {password}")

        user = User.query.filter_by(username=username).first()
        if username == 'maaz' and not user:
            session['username'] = username
            return redirect(url_for('signup'))
        if user and not user.password_set:
            session['username'] = username
            return redirect(url_for('signup'))
        if username is not None:
            user = User.query.filter_by(username=username).first()
            if user is None:
                flash('User not found with this Username', 'danger')
                return render_template('login.html', username=username)
        else:
            flash('Please Enter a Valid Username', 'danger')
            return render_template('login.html', username=username)

        if password is not None:
            if check_password_hash(user.password, password):
                print('here')
                response = request.form.get('g-recaptcha-response')
                print('response here, ', response)
                verify_response = requests.post(url=f'https://www.google.com/recaptcha/api/siteverify?secret=6LeSpToqAAAAAFzsOXazHma0WARwovmBlwv1Px6q&response={response}')
                verify_response_json = verify_response.json()
                print(verify_response_json)

                # Now you can check the 'success' field
                if not verify_response_json.get('success'):
                    abort(401)

                if not user.wrong_login_tries or user.wrong_login_tries < 3:
                    user.wrong_login_tries = 0
                    db.session.commit()
                    login_user(user)
                else:
                    session['username'] = user.username
                    session['user_id'] = user.id
                    return redirect(url_for('twoFactorAuthentication'))
                return redirect(url_for('index'))
            else:
                flash('Incorrect Username or Password', 'danger')
                if user.wrong_login_tries:
                    user.wrong_login_tries += 1
                else:
                    user.wrong_login_tries = 1

                db.session.commit()
                return render_template('login.html', username=username)
        else:
            flash('Please Enter a valid Password', 'danger')
            return render_template('login.html', username=username)

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))

    if request.method == 'POST':
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')
        name = request.form.get('name')
        address = request.form.get('address')
        country = request.form.get('country')

        print(username, password1, password2, name, address, country)
        if not name or not address or not country or not username or not password1 or not password2:
            flash('Please Input All Fields.', 'danger')
            return render_template('signup.html', username=username, name=name, address=address, country=country)

        user = User.query.filter_by(username=username).first()
        if user and user.password_set:
            flash('User already exists with this Username', 'danger')
            return render_template('signup.html', username=username, name=name, address=address, country=country)
        else:
            if not user:
                user = User()
                consultant = Consultant()
            else:
                consultant = Consultant.query.get(user.consultant_id)

        if password1 != password2:
            flash('The two passwords does not match. Please try again', 'danger')
            return render_template('signup.html', username=username, name=name, address=address, country=country)

        hashed_password = generate_password_hash(password1, 'scrypt')

        try:
            consultant.name = name
            consultant.address = address
            consultant.country = country
            db.session.add(consultant)
            db.session.commit()
            user.username = username
            user.password = hashed_password
            user.consultant_id = consultant.id
            if user.username == 'maaz':
                user.is_admin = True
            user.password_set = True
            db.session.add(user)
            db.session.commit()
            session.pop('username', None)
            flash('Password created successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Unexpected Error occurred.' + str(e), 'danger')
            return render_template('signup.html')

    return render_template('signup.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('error-pages/404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    # note that we set the 404 status explicitly
    return render_template('error-pages/500.html'), 500


# with app.app_context():
#     db.drop_all()
# with app.app_context():
#     db.create_all()

@app.route('/payments/request-payment', methods=['POST'])
@csrf.exempt
def request_payment():
    try:
        print('here')
        data = request.get_json()

        custom_message = data.get('message')
        project = data.get('project')

        sendEmail("Umer", custom_message, project)

        # Mock response for demonstration
        result = True  # or False depending on your logic

        if result:
            return jsonify({"status": "success"})
    except Exception as e:
        print(e)
        return jsonify({"status": "failed"})



if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
