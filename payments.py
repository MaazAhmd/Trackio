import calendar
import json
from io import BytesIO

import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, make_response, jsonify
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta

from flask_wtf.csrf import validate_csrf

from helping_functions import admin_required, sendEmail
from models import Client, db, Project, ProjectConsultant, TimeEntry, Consultant, User, cache

payments = Blueprint('payments', __name__)


@payments.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
@cache.cached(timeout=5)
def all_payments():
    clients = Client.query
    projects = Project.query
    consultants = Consultant.query

    # Filter clients based on the request arguments
    filter_applied = False
    filter_client_name = None
    filter_project_name = None
    filter_consultant_name = None

    filter_clients = request.args.get('filter_clients')
    if filter_clients and filter_clients != 'all':
        filter_applied = True
        clients = clients.filter_by(id=int(filter_clients)).all()
        filter_client_name = clients[0].name
    else:
        clients = clients.all()

    filter_consultants = request.args.get('filter_consultants')
    if filter_consultants and filter_consultants != 'all':
        filter_applied = True
        consultants = consultants.filter_by(id=int(filter_consultants)).all()
        filter_consultant_name = consultants[0].name
    else:
        consultants = consultants.all()

    filter_projects = request.args.get('filter_projects')
    if filter_projects and filter_projects != 'all':
        filter_applied = True
        if filter_clients:
            projects = projects.filter(Project.customer_id.in_([client.id for client in clients]))
        projects = projects.filter_by(id=int(filter_projects)).all()
        if len(projects) > 0:
            filter_project_name = projects[0].name
    else:
        if filter_clients:
            projects = projects.filter(Project.customer_id.in_([client.id for client in clients]))
        projects = projects.all()

    projectConsultants = ProjectConsultant.query.filter(
        ProjectConsultant.consultant_id.in_([consultant.id for consultant in consultants]),
        ProjectConsultant.project_id.in_([project.id for project in projects])
    ).all()

    data = []

    time_filter = request.args.get('filter_time')
    if not time_filter:
        time_filter = 'all-time'

    today = date.today()
    start_date = None
    end_date = None
    start_date_filter = None
    end_date_filter = None
    if time_filter == 'custom':
        start_date_filter = request.args.get('start_date_filter')
        end_date_filter = request.args.get('end_date_filter')

        if start_date_filter and end_date_filter:
            try:
                start_date = datetime.strptime(start_date_filter, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_filter, '%Y-%m-%d').date()
            except ValueError:
                # Handle invalid date format
                return "Invalid date format", 400
        else:
            # Handle missing dates
            return "Start date and end date are required for custom filter", 400

    elif time_filter == 'this-month':
        start_date = today.replace(day=1)
        last_day_of_current_month = calendar.monthrange(today.year, today.month)[1]
        end_date = today.replace(day=last_day_of_current_month)
    elif time_filter == 'last-month':
        first_day_of_current_month = today.replace(day=1)
        last_day_of_last_month = first_day_of_current_month - timedelta(days=1)
        start_date = last_day_of_last_month.replace(day=1)
        end_date = last_day_of_last_month
    elif time_filter == 'this-year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    elif time_filter == 'last-year':
        start_date = today.replace(year=today.year - 1, month=1, day=1)
        end_date = today.replace(year=today.year - 1, month=12, day=31)
    elif time_filter == 'all-time':
        start_date = None
        end_date = None

    total_billable_amount = {}
    paid_amount = {}
    left_amount = {}

    for projectConsultant in projectConsultants:
        project = Project.query.get(projectConsultant.project_id)
        consultant = Consultant.query.get(projectConsultant.consultant_id)
        client = Client.query.get(project.customer_id)
        user = User.query.filter_by(consultant_id=consultant.id).first()
        if user.is_admin:
            continue
        if start_date and end_date:
            if not project.end_date >= start_date:
                continue
            if not project.end_date <= end_date:
                continue
        if projectConsultant.hourly:
            continue

        currency = projectConsultant.currency.upper()
        if currency in total_billable_amount:
            total_billable_amount[currency] += projectConsultant.price
        else:
            total_billable_amount[currency] = projectConsultant.price

        if projectConsultant.paid:
            if currency in paid_amount:
                paid_amount[currency] += projectConsultant.price
            else:
                paid_amount[currency] = projectConsultant.price
        else:
            if currency in left_amount:
                left_amount[currency] += projectConsultant.remaining_price
            else:
                left_amount[currency] = projectConsultant.remaining_price


        data.append(
            {'project_name': project.name, 'client_name': client.name, 'consultant_name': consultant.name,
             'price': f"{projectConsultant.price:.0f}", 'currency': projectConsultant.currency.upper(),
             'paid': projectConsultant.paid, 'remaining_price': f"{projectConsultant.remaining_price:.0f}",
             'id': projectConsultant.id})

        # data.append({'project_name': project.name, 'client_name': client.name, 'consultant_name': consultant.name,
        #              'notes': notes,
        #              'billable_amount': billable_amount, 'billable_duration': billable_duration,
        #              'non_billable_duration': non_billable_duration})

    total_amount_str = ', '.join([f"{currency} {amount:.0f}" for currency, amount in total_billable_amount.items()])
    paid_amount_str = ', '.join([f"{currency} {amount:.0f}" for currency, amount in paid_amount.items()])
    left_amount_str = ', '.join([f"{currency} {amount:.0f}" for currency, amount in left_amount.items()])

    # search = request.args.get('search')
    # if search:
    #     search_term = search.lower()
    #     filtered_data = []
    #     for entry in data:
    #         if (search_term in entry.get('project_name', '').lower() or
    #                 search_term in entry.get('client_name', '').lower() or
    #                 search_term in entry.get('consultant_name', '').lower() or
    #                 search_term in entry.get('notes', '').lower() or
    #                 search_term in str(entry.get('billable_amount', '')).lower() or
    #                 search_term in str(entry.get('billable_duration', '')).lower() or
    #                 search_term in str(entry.get('non_billable_duration', '')).lower()):
    #             filtered_data.append(entry)
    #     data = filtered_data

    sort = request.args.get('sort')
    if sort:
        sort_key = None
        reverse = False

        if sort == 'client-asc':
            sort_key = 'client_name'
            reverse = False
        elif sort == 'client-desc':
            sort_key = 'client_name'
            reverse = True
        elif sort == 'project-asc':
            sort_key = 'project_name'
            reverse = False
        elif sort == 'project-desc':
            sort_key = 'project_name'
            reverse = True
        elif sort == 'consultant-asc':
            sort_key = 'consultant_name'
            reverse = False
        elif sort == 'consultant-desc':
            sort_key = 'consultant_name'
            reverse = True

        if sort_key:
            data = sorted(data, key=lambda x: x.get(sort_key, ''), reverse=reverse)

    return render_template('index.html', page='payments', data=data, all_clients=clients,
                           all_projects=projects, all_consultants=consultants, filter_projects=filter_projects,
                           filter_consultants=filter_consultants, filter_clients=filter_clients,
                           filter_project_name=filter_project_name, filter_consultant_name=filter_consultant_name,
                           filter_client_name=filter_client_name, filter=filter_applied,
                           filter_time=time_filter,
                           start_date_filter=start_date_filter, end_date_filter=end_date_filter,
                           total_amount_str=total_amount_str, paid_amount_str=paid_amount_str, left_amount_str=left_amount_str)



@payments.route('/paid', methods=['POST'])
@login_required
@admin_required
def paid():
    id = request.form.get('id')
    amount = request.form.get('amount')
    project_consultant = ProjectConsultant.query.get_or_404(id)
    if not amount:
        flash("Amount is required")
        return redirect(url_for('payments.all_payments'))
    try:
        amount = float(amount)
    except ValueError:
        flash("Amount must be numeric")
        return redirect(url_for('payments.all_payments'))

    if amount > project_consultant.remaining_price:
        flash("Amount must be less than or equal to project price")
        return redirect(url_for('payments.all_payments'))
    new_remaining_amount = project_consultant.remaining_price - amount
    if new_remaining_amount == 0:
        project_consultant.paid = True

    project_consultant.remaining_price = new_remaining_amount
    db.session.add(project_consultant)
    db.session.commit()
    flash("Successfully updated Record", "success")
    return redirect(url_for('payments.all_payments'))


@payments.route('/unpaid', methods=['POST'])
@login_required
@admin_required
def unpaid():
    id = request.form.get('id')
    project_consultant = ProjectConsultant.query.get_or_404(id)
    project_consultant.paid = False
    project_consultant.remaining_price = project_consultant.price
    db.session.add(project_consultant)
    db.session.commit()
    flash("Successfully updated Record", "success")
    return redirect(url_for('payments.all_payments'))


@payments.route('/my-payments', methods=['GET', 'POST'])
@login_required
def consultant_payments():
    if current_user.is_admin:
        flash("This Page is not for You!", 'danger')
        return redirect(url_for('login'))

    consultant_id = current_user.consultant_id

    filter_applied = False

    project_consultants = ProjectConsultant.query.filter_by(consultant_id=consultant_id).all()

    data = []

    time_filter = request.args.get('filter_time')
    if not time_filter:
        time_filter = 'all-time'

    today = date.today()
    start_date = None
    end_date = None
    start_date_filter = None
    end_date_filter = None

    if time_filter == 'custom':
        start_date_filter = request.args.get('start_date_filter')
        end_date_filter = request.args.get('end_date_filter')

        if start_date_filter and end_date_filter:
            try:
                start_date = datetime.strptime(start_date_filter, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_filter, '%Y-%m-%d').date()
            except ValueError:
                # Handle invalid date format
                return "Invalid date format", 400
        else:
            # Handle missing dates
            return "Start date and end date are required for custom filter", 400

    elif time_filter == 'this-month':
        start_date = today.replace(day=1)
        last_day_of_current_month = calendar.monthrange(today.year, today.month)[1]
        end_date = today.replace(day=last_day_of_current_month)
    elif time_filter == 'last-month':
        first_day_of_current_month = today.replace(day=1)
        last_day_of_last_month = first_day_of_current_month - timedelta(days=1)
        start_date = last_day_of_last_month.replace(day=1)
        end_date = last_day_of_last_month
    elif time_filter == 'this-year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    elif time_filter == 'last-year':
        start_date = today.replace(year=today.year - 1, month=1, day=1)
        end_date = today.replace(year=today.year - 1, month=12, day=31)
    elif time_filter == 'all-time':
        start_date = None
        end_date = None

    total_billable_amount = {}
    paid_amount = {}
    left_amount = {}

    for projectConsultant in project_consultants:
        project = Project.query.get(projectConsultant.project_id)
        user = User.query.filter_by(consultant_id=consultant_id).first()
        if user.is_admin:
            continue
        if start_date and end_date:
            if not project.end_date >= start_date:
                continue
            if not project.end_date <= end_date:
                continue
        if projectConsultant.hourly:
            continue

        currency = projectConsultant.currency.upper()
        if currency in total_billable_amount:
            total_billable_amount[currency] += projectConsultant.price
        else:
            total_billable_amount[currency] = projectConsultant.price

        if projectConsultant.paid:
            if currency in paid_amount:
                paid_amount[currency] += projectConsultant.price
            else:
                paid_amount[currency] = projectConsultant.price
        else:
            if currency in left_amount:
                left_amount[currency] += projectConsultant.remaining_price
            else:
                left_amount[currency] = projectConsultant.remaining_price

        data.append(
            {'project_name': project.name, 'price': f"{projectConsultant.price:.0f}", 'currency': projectConsultant.currency.upper(),
             'paid': projectConsultant.paid, 'remaining_price': f"{projectConsultant.remaining_price:.0f}",
             'id': projectConsultant.id})

    total_amount_str = ', '.join([f"{currency} {amount:.0f}" for currency, amount in total_billable_amount.items()])
    paid_amount_str = ', '.join([f"{currency} {amount:.0f}" for currency, amount in paid_amount.items()])
    left_amount_str = ', '.join([f"{currency} {amount:.0f}" for currency, amount in left_amount.items()])

    search = request.args.get('search')
    if search:
        search_term = search.lower()
        filtered_data = []
        for entry in data:
            if (search_term in entry.get('project_name', '').lower() or
                    search_term in str(entry.get('price', '')).lower() or
                    search_term in str(entry.get('currency', '')).lower()):
                filtered_data.append(entry)
        data = filtered_data

    # sort = request.args.get('sort')
    # if sort:
    #     sort_key = None
    #     reverse = False
    #
    #     if sort == 'client-asc':
    #         sort_key = 'client_name'
    #         reverse = False
    #     elif sort == 'client-desc':
    #         sort_key = 'client_name'
    #         reverse = True
    #     elif sort == 'project-asc':
    #         sort_key = 'project_name'
    #         reverse = False
    #     elif sort == 'project-desc':
    #         sort_key = 'project_name'
    #         reverse = True
    #     elif sort == 'consultant-asc':
    #         sort_key = 'consultant_name'
    #         reverse = False
    #     elif sort == 'consultant-desc':
    #         sort_key = 'consultant_name'
    #         reverse = True
    #
    #     if sort_key:
    #         data = sorted(data, key=lambda x: x.get(sort_key, ''), reverse=reverse)

    return render_template('index.html', page='consultant-payments', data=data,
                           filter=filter_applied,
                           filter_time=time_filter,
                           start_date_filter=start_date_filter, end_date_filter=end_date_filter,
                           total_amount_str=total_amount_str, paid_amount_str=paid_amount_str, left_amount_str=left_amount_str)


@payments.route('/export-csv', methods=['POST'])
@admin_required
@login_required
def exportCSV():
    data_json = request.form.get('data')
    data = json.loads(data_json)

    # Convert data to DataFrame
    df = pd.DataFrame(data)

    # Export to CSV
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    return send_file(csv_buffer, mimetype='text/csv', as_attachment=True, download_name='Payments.csv')


@payments.route('/export-excel', methods=['POST'])
@admin_required
@login_required
def exportExcel():
    data_json = request.form.get('data')
    data = json.loads(data_json)

    # Convert data to DataFrame
    df = pd.DataFrame(data)

    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    excel_buffer.seek(0)

    return send_file(excel_buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='Payments.xlsx')
