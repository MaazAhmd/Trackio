from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user

from helping_functions import admin_required
from models import CommunicationTime, db, Project, ProjectConsultant

communication_times_blueprint = Blueprint('communication_times', __name__)


@communication_times_blueprint.route('/')
@communication_times_blueprint.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_communication_times(id=None):
    query_date = request.args.get('date')
    if not query_date:
        tracking_datetime = datetime.now()
    else:
        if query_date == 'today':
            tracking_datetime = datetime.now()
        else:
            try:
                tracking_datetime = datetime.strptime(query_date, '%Y-%m-%d %H:%M:%S.%f')
            except ValueError as e:
                try:
                    tracking_datetime = datetime.strptime(query_date, '%Y-%m-%d')
                except ValueError as e:
                    tracking_datetime = datetime.strptime(query_date, '%Y-%m-%d %H:%M:%S')

    if tracking_datetime.date() == datetime.now().date():
        today = True
    else:
        today = False

    tracking_date = tracking_datetime.date()
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    tracking_day = days[tracking_datetime.weekday()]


    five_day_array = [tracking_datetime - timedelta(days=2), tracking_datetime - timedelta(days=1), tracking_datetime,
                      tracking_datetime + timedelta(days=1), tracking_datetime + timedelta(days=2)]

    if id:
        if not current_user.is_admin:
            logout_user()
            flash("You cannot access that page.")
            return redirect(url_for('login'))

    if current_user.is_admin:
        communication_times = CommunicationTime.query.filter_by(date=tracking_datetime.date()).all()
    else:
        communication_times = None

    communication_time = CommunicationTime.query.get(id)
    if id is not None:
        if not communication_time:
            flash('Communication Time Entry not found with this id.', 'danger')
            return redirect(url_for('communication_times.manage_communication_times'))
        else:
            if request.method == 'POST':
                if not communication_time:
                    communication_time = CommunicationTime()
                hours = request.form.get('hours')
                minutes = request.form.get('minutes')
                description = request.form.get('description')
                if not minutes or not description or not hours:
                    flash('All fields are required', 'danger')
                    return render_template('index.html', page='view-communication_times', communication_times=communication_times, id=id, tracking_date=tracking_datetime, tracking_day=tracking_day, five_day_array=five_day_array, today=today)
                communication_time.hours = hours
                communication_time.minutes = minutes
                communication_time.description = description
                db.session.add(communication_time)
                db.session.commit()
                return redirect(url_for('communication_times.manage_communication_times', date=communication_time.date))

    return render_template('index.html', page='view-communication-times', communication_times=communication_times, id=id, tracking_date=tracking_datetime, tracking_day=tracking_day, five_day_array=five_day_array, today=today)


@communication_times_blueprint.route('/add', methods=['POST'])
@login_required
@admin_required
def add_communication_time():
    if request.method == 'POST':
        communication_time = CommunicationTime()
        communication_time.hours = request.form.get('hours')
        communication_time.minutes = request.form.get('minutes')
        communication_time.description = request.form.get('description')
        date = request.form.get('date')
        communication_time.date = date

        if not communication_time.minutes or not communication_time.description or not communication_time.date or not communication_time.hours:
            flash('All fields are required', 'danger')
            return redirect(url_for('communication_times.manage_communication_times', date=date))

        db.session.add(communication_time)
        db.session.commit()
        return redirect(url_for('communication_times.manage_communication_times', date=date))
    # return render_template('index.html', page='add_communication_time', communication_time=communication_time)


@communication_times_blueprint.route('/communication_times/delete/<int:id>', methods=['GET'])
@login_required
@admin_required
def delete_communication_time(id):
    date = request.args.get('date')
    communication_time = CommunicationTime.query.get(id)
    # projects = Project.query.all()
    # for project in projects:
    #     if project.customer_id == id:
    #         flash("Error deleting Time Entry. It has project/s associated with them.", "danger")
    #         return redirect(url_for('communication_times.manage_communication_times', date=date))
    db.session.delete(communication_time)
    db.session.commit()
    return redirect(url_for('communication_times.manage_communication_times', date=date))


