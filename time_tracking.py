from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta, time
from sqlalchemy import asc

from models import Client, db, Project, ProjectConsultant, TimeEntry
time_tracking = Blueprint('time_tracking', __name__)

def create_and_check_time_entries(project_consultant_id, tracking_date):
    time_entry = TimeEntry.query.filter_by(project_consultant_id=project_consultant_id, performance_date=tracking_date).all()
    if time_entry is None or len(time_entry) == 0:
        new_time_entry = TimeEntry(project_consultant_id=project_consultant_id,  performance_date=tracking_date)
        db.session.add(new_time_entry)
        db.session.commit()

@time_tracking.route('/track-time')
@login_required
def track_time():
    consultant_id = current_user.consultant_id
    query_date = request.args.get('date')
    if not query_date:
        tracking_datetime = datetime.now()
    else:
        if query_date == 'today':
            tracking_datetime = datetime.now()
        else:
            tracking_datetime = datetime.strptime(query_date, '%Y-%m-%d %H:%M:%S.%f')

    if tracking_datetime.date() == datetime.now().date():
        today = True
    else:
        today = False

    tracking_date = tracking_datetime.date()
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    tracking_day = days[tracking_datetime.weekday()]
    time_entries_with_project = []
    clients = []
    five_day_array = [tracking_datetime - timedelta(days=2), tracking_datetime - timedelta(days=1), tracking_datetime, tracking_datetime + timedelta(days=1), tracking_datetime + timedelta(days=2)]

    project_consultants = ProjectConsultant.query.filter_by(consultant_id=consultant_id).all()
    for project_consultant in project_consultants:
        project = Project.query.get(project_consultant.project_id)
        print(project.start_date, tracking_date, project.end_date)
        if not project.start_date <= tracking_date <= project.end_date:
            continue
        if not project.active:
            continue
        create_and_check_time_entries(project_consultant.id, tracking_date)
        project_time_entries = TimeEntry.query.filter_by(project_consultant_id=project_consultant.id, performance_date=tracking_date).order_by(asc(TimeEntry.id)).all()

        time_entries_with_project.append({'project': project, 'time_entry': project_time_entries})
        client = Client.query.get(project.customer_id)
        if client not in clients:
            clients.append(client)

    return render_template('index.html', page='time-tracking', time_entries=time_entries_with_project, clients=clients, tracking_date=tracking_datetime, tracking_day=tracking_day, five_day_array=five_day_array, today=today)


@time_tracking.route('/track_time/add', methods=['POST'])
@login_required
def add_time_entry():
    time_entry_id = request.form.get('time_entry_id')
    given_date = request.form.get('tracking_date')
    tracking_datetime = datetime.strptime(given_date, '%Y-%m-%d %H:%M:%S.%f')
    tracking_date = tracking_datetime.date()

    # Editing time entry:
    edit = request.form.get('edit')
    if edit:
        edit_entry = TimeEntry.query.get(edit)
        edit_entry.tracked = False
        db.session.add(edit_entry)
        db.session.commit()
        return redirect(url_for('time_tracking.track_time', date=tracking_datetime))

    description = request.form.get('description')
    hours = request.form.get('hours')
    minutes = request.form.get('minutes')

    entry = TimeEntry.query.get(time_entry_id)
    project = Project.query.get(ProjectConsultant.query.get(entry.project_consultant_id).project_id)

    entry.description = description
    entry.hours = hours
    entry.minutes = minutes
    entry.tracked = True
    if request.form.get('billable'):
        entry.billable = True
    elif project.price:
        entry.billable = True
    else:
        entry.billable = False
    db.session.add(entry)
    db.session.commit()

    return redirect(url_for('time_tracking.track_time', date=tracking_datetime))


@time_tracking.route('/track_time/create_time_entry', methods=['POST'])
@login_required
def create_time_entry():
    consultant_id = current_user.consultant_id
    project_id = request.form.get('project_id')
    project_consultant = ProjectConsultant.query.filter_by(consultant_id=consultant_id, project_id=project_id).first()
    tracking_date = request.form.get('tracking_date')
    try:
        new_time_entry = TimeEntry(project_consultant_id=project_consultant.id, performance_date=tracking_date)
        db.session.add(new_time_entry)
        db.session.commit()
    except Exception as e:
        print(e)
        db.session.rollback()

    return redirect(url_for('time_tracking.track_time', date=tracking_date))


@time_tracking.route('delete_time_entry/<int:id>', methods=['GET'])
@login_required
def delete_time_entry(id):
    time_entry = TimeEntry.query.get(id)
    if not time_entry:
        flash('No entry with that id was found.', 'danger')
        return redirect('track_time')
    given_date = time_entry.performance_date
    print(given_date)
    tracking_datetime = datetime.combine(given_date, time(0, 0, 0, 23120))
    print(tracking_datetime)
    db.session.delete(time_entry)
    db.session.commit()
    return redirect(url_for('time_tracking.track_time', date=tracking_datetime))


