import calendar
import json
from io import BytesIO

import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, make_response
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta

from sqlalchemy import asc, desc
from models import Client, db, Project, ProjectConsultant, TimeEntry, Consultant, CommunicationTime

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import io
time_entries = Blueprint('time_entries', __name__)


@time_entries.route('/time_entries', methods=['GET', 'POST'])
@login_required
def view_time_entries():
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
        time_filter = 'this-month'

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

    total_billable_duration = 0
    total_non_billable_duration = 0
    total_billable_amount = {}

    projects_calculated = []

    project_ids = [pc.project_id for pc in projectConsultants]
    projects = Project.query.filter(Project.id.in_(project_ids)).all()
    project_dict = {project.id: project for project in projects}

    customer_ids = {project.customer_id for project in projects}
    clients = Client.query.filter(Client.id.in_(customer_ids)).all()
    client_dict = {client.id: client for client in clients}

    consultant_ids = {pc.consultant_id for pc in projectConsultants}
    consultants = Consultant.query.filter(Consultant.id.in_(consultant_ids)).all()
    consultant_dict = {consultant.id: consultant for consultant in consultants}

    # Step 1: Extract all unique project_consultant_ids from projectConsultants
    project_consultant_ids = [pc.id for pc in projectConsultants]

    # Step 2: Fetch all relevant TimeEntry records in a single query
    if start_date and end_date:
        time_entries = TimeEntry.query.filter(
            TimeEntry.project_consultant_id.in_(project_consultant_ids),
            TimeEntry.performance_date >= start_date,
            TimeEntry.performance_date <= end_date
        ).all()
    else:
        time_entries = TimeEntry.query.filter(
            TimeEntry.project_consultant_id.in_(project_consultant_ids)
        ).all()

    # Step 3: Create a dictionary mapping project_consultant_id to list of TimeEntry objects
    time_entries_dict = {}
    for entry in time_entries:
        if entry.project_consultant_id not in time_entries_dict:
            time_entries_dict[entry.project_consultant_id] = []
        time_entries_dict[entry.project_consultant_id].append(entry)

    for projectConsultant in projectConsultants:
        project = project_dict.get(projectConsultant.project_id)
        consultant = consultant_dict.get(projectConsultant.consultant_id)
        client = client_dict.get(project.customer_id)
        related_entries = time_entries_dict.get(projectConsultant.id, [])

        for entry in related_entries:
            considerable_duration = 0
            if entry.tracked:
                considerable_duration += (entry.hours * 60)
                considerable_duration += entry.minutes

                # entry_billable_duration = entry.hours * 60
                # entry_billable_duration += entry.minutes

                billable_duration_hours = considerable_duration // 60
                billable_duration_mins = considerable_duration % 60

                billable_formatted_hours = f"{billable_duration_hours:02}"
                billable_formatted_mins = f"{billable_duration_mins:02}"

                if entry.billable:
                    # that means Hourly:
                    if not project.price:
                        billable_duration_str = f"{billable_formatted_hours}:{billable_formatted_mins}"
                        non_billable_duration_str = "00:00"
                        total_billable_duration += considerable_duration
                        if not projectConsultant.price:
                            billable_amount = "No Hourly Rate Set"
                        else:
                            billable_amount = round((considerable_duration / 60) * projectConsultant.price, 2)
                            currency = client.currency.upper()
                            if currency in total_billable_amount:
                                total_billable_amount[currency] += billable_amount
                            else:
                                total_billable_amount[currency] = billable_amount
                            billable_amount = f'{currency} {billable_amount:.2f}'
                    # that means NOT Hourly:
                    else:
                        billable_duration_str = f"{billable_formatted_hours}:{billable_formatted_mins}"
                        non_billable_duration_str = "N/A"
                        total_billable_duration += considerable_duration
                        currency = client.currency.upper()

                        billable_amount = project.price
                        billable_amount = f'Fixed {currency} {billable_amount:.2f}'

                else:
                    total_non_billable_duration += considerable_duration
                    non_billable_duration_str = f"{billable_formatted_hours}:{billable_formatted_mins}"
                    billable_duration_str = "00:00"
                    billable_amount = "Not Applicable"

                data.append(
                    {'project_name': project.name, 'client_name': client.name, 'consultant_name': consultant.name,
                     'notes': entry.description,
                     'billable_amount': billable_amount, 'billable_duration': billable_duration_str,
                     'non_billable_duration': non_billable_duration_str, 'date': entry.performance_date})

        # data.append({'project_name': project.name, 'client_name': client.name, 'consultant_name': consultant.name,
        #              'notes': notes,
        #              'billable_amount': billable_amount, 'billable_duration': billable_duration,
        #              'non_billable_duration': non_billable_duration})

        if project.price:
            if project.id not in projects_calculated:
                if project.end_date > start_date and project.end_date < end_date:
                    currency = client.currency.upper()
                    if currency in total_billable_amount:
                        total_billable_amount[currency] += project.price
                    else:
                        total_billable_amount[currency] = project.price
                    projects_calculated.append(project.id)

    total_billable_duration_hours = total_billable_duration // 60
    total_billable_duration_mins = total_billable_duration % 60
    total_non_billable_duration_hours = total_non_billable_duration // 60
    total_non_billable_duration_mins = total_non_billable_duration % 60
    total_billable_duration_str = f"{total_billable_duration_hours:02}:{total_billable_duration_mins:02}"
    total_non_billable_duration_str = f"{total_non_billable_duration_hours:02}:{total_non_billable_duration_mins:02}"
    total_amount_str = ', '.join([f"{currency} {amount:.2f}" for currency, amount in total_billable_amount.items()])

    communication_times = CommunicationTime.query.filter(
        CommunicationTime.date >= start_date,
        CommunicationTime.date <= end_date
    ).all()
    total_mins = 0
    for communication_time in communication_times:
        total_mins += communication_time.hours * 60
        total_mins += communication_time.minutes

    total_communication_hours = total_mins // 60
    total_communication_mins = total_mins % 60
    total_communication_time_str = f"{total_communication_hours:02}:{total_communication_mins:02}"

    search = request.args.get('search')
    if search:
        search_term = search.lower()
        filtered_data = []
        for entry in data:
            if (search_term in entry.get('project_name', '').lower() or
                    search_term in entry.get('client_name', '').lower() or
                    search_term in entry.get('consultant_name', '').lower() or
                    search_term in entry.get('notes', '').lower() or
                    search_term in str(entry.get('billable_amount', '')).lower() or
                    search_term in str(entry.get('billable_duration', '')).lower() or
                    search_term in str(entry.get('non_billable_duration', '')).lower()):
                filtered_data.append(entry)
        data = filtered_data

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

    data = sorted(data, key=lambda x: x.get('date', ''), reverse=True)

    return render_template('index.html', page='time-entries', data=data, all_clients=clients,
                           all_projects=projects, all_consultants=consultants, filter_projects=filter_projects,
                           filter_consultants=filter_consultants, filter_clients=filter_clients,
                           filter_project_name=filter_project_name, filter_consultant_name=filter_consultant_name,
                           filter_client_name=filter_client_name, search=search, filter=filter_applied,
                           filter_time=time_filter,
                           start_date_filter=start_date_filter, end_date_filter=end_date_filter,
                           total_billable_duration_str=total_billable_duration_str,
                           total_non_billable_duration_str=total_non_billable_duration_str,
                           total_amount_str=total_amount_str, total_communication_time_str=total_communication_time_str)


@time_entries.route('/export-time-entries-csv', methods=['POST'])
def exportCSV():
    data_json = request.form.get('data')
    data = json.loads(data_json)

    # Convert data to DataFrame
    df = pd.DataFrame(data)

    # Export to CSV
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    return send_file(csv_buffer, mimetype='text/csv', as_attachment=True, download_name='TimeEntries.csv')


@time_entries.route('/export-time-entries-excel', methods=['POST'])
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
                     as_attachment=True, download_name='TimeEntries.xlsx')


@time_entries.route('/time_entries/pdf')
@login_required
def time_entries_pdf():
    all_clients = Client.query.all()
    all_projects = Project.query.all()
    all_consultants = Consultant.query.all()

    projectConsultants = ProjectConsultant.query.all()
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
        time_filter = 'this-month'

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

    total_billable_duration = 0
    total_non_billable_duration = 0
    total_billable_amount = {}
    for projectConsultant in projectConsultants:
        project = Project.query.get(projectConsultant.project_id)
        consultant = Consultant.query.get(projectConsultant.consultant_id)
        client = Client.query.get(project.customer_id)
        if start_date and end_date:
            related_entries = TimeEntry.query.filter(
                TimeEntry.project_consultant_id == projectConsultant.id,
                TimeEntry.performance_date >= start_date,
                TimeEntry.performance_date <= end_date
            ).all()
        else:
            related_entries = TimeEntry.query.filter_by(project_consultant_id=projectConsultant.id).all()

        for entry in related_entries:
            considerable_duration = 0
            if entry.tracked:
                considerable_duration += (entry.hours * 60)
                considerable_duration += entry.minutes

                # entry_billable_duration = entry.hours * 60
                # entry_billable_duration += entry.minutes

                billable_duration_hours = considerable_duration // 60
                billable_duration_mins = considerable_duration % 60

                billable_formatted_hours = f"{billable_duration_hours:02}"
                billable_formatted_mins = f"{billable_duration_mins:02}"

                if entry.billable:
                    billable_duration_str = f"{billable_formatted_hours}:{billable_formatted_mins}"
                    non_billable_duration_str = "00:00"
                    total_billable_duration += considerable_duration
                    if not projectConsultant.price:
                        billable_amount = "No Hourly Rate Set"
                    else:
                        billable_amount = round((considerable_duration / 60) * projectConsultant.price, 2)
                        currency = client.currency.upper()
                        if currency in total_billable_amount:
                            total_billable_amount[currency] += billable_amount
                        else:
                            total_billable_amount[currency] = billable_amount
                        billable_amount = f'{currency} {billable_amount:.2f}'
                else:
                    total_non_billable_duration += considerable_duration
                    non_billable_duration_str = f"{billable_formatted_hours}:{billable_formatted_mins}"
                    billable_duration_str = "00:00"
                    billable_amount = "Not Applicable"

                data.append(
                    {'project_name': project.name, 'client_name': client.name, 'consultant_name': consultant.name,
                     'notes': entry.description,
                     'billable_amount': billable_amount, 'billable_duration': billable_duration_str,
                     'non_billable_duration': non_billable_duration_str})

        # data.append({'project_name': project.name, 'client_name': client.name, 'consultant_name': consultant.name,
        #              'notes': notes,
        #              'billable_amount': billable_amount, 'billable_duration': billable_duration,
        #              'non_billable_duration': non_billable_duration})

    total_billable_duration_hours = total_billable_duration // 60
    total_billable_duration_mins = total_billable_duration % 60
    total_non_billable_duration_hours = total_non_billable_duration // 60
    total_non_billable_duration_mins = total_non_billable_duration % 60
    total_billable_duration_str = f"{total_billable_duration_hours:02}:{total_billable_duration_mins:02}"
    total_non_billable_duration_str = f"{total_non_billable_duration_hours:02}:{total_non_billable_duration_mins:02}"
    total_amount_str = ', '.join([f"{currency} {amount:.2f}" for currency, amount in total_billable_amount.items()])

    search = request.args.get('search')
    if search:
        search_term = search.lower()
        filtered_data = []
        for entry in data:
            if (search_term in entry.get('project_name', '').lower() or
                    search_term in entry.get('client_name', '').lower() or
                    search_term in entry.get('consultant_name', '').lower() or
                    search_term in entry.get('notes', '').lower() or
                    search_term in str(entry.get('billable_amount', '')).lower() or
                    search_term in str(entry.get('billable_duration', '')).lower() or
                    search_term in str(entry.get('non_billable_duration', '')).lower()):
                filtered_data.append(entry)
        data = filtered_data

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

    print(data)

    buffer = io.BytesIO()

    # Create a PDF document
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    # Define styles
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = styles['Title']
    heading_style = ParagraphStyle(name='Heading', fontName='Helvetica-Bold', fontSize=14, alignment=1, spaceBefore=16, spaceAfter=24)
    subheading_style = ParagraphStyle(name='Subheading', fontName='Helvetica-Bold', fontSize=12, alignment=0,
                                      spaceAfter=6)
    normal_style = styles['Normal']
    table_cell_style = ParagraphStyle(name='TableCell', fontName='Helvetica', fontSize=10, leading=12, wordWrap=True)

    # Prepare data for the PDF
    table_data = [
        [Paragraph("Client", table_cell_style), Paragraph("Project", table_cell_style),
         Paragraph("Consultant", table_cell_style), Paragraph("Notes", table_cell_style),
         Paragraph("Billable Duration", table_cell_style), Paragraph("Non-Billable Duration", table_cell_style),
         Paragraph("Amount", table_cell_style)],
    ]

    for entry in data:
        table_data.append([
            Paragraph(entry['client_name'], table_cell_style),
            Paragraph(entry['project_name'], table_cell_style),
            Paragraph(entry['consultant_name'], table_cell_style),
            Paragraph(entry['notes'], table_cell_style),
            Paragraph(entry['billable_duration'], table_cell_style),
            Paragraph(entry['non_billable_duration'], table_cell_style),
            Paragraph(entry['billable_amount'], table_cell_style)
        ])

    # Create a Table object with the data
    table = Table(table_data,
                  colWidths=[1.0 * inch, 1.0 * inch, 1.0 * inch, 2.0 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch])

    # Define table style
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONT', (0, 1), (-1, -1), 'Helvetica'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ])

    table.setStyle(style)

    # Create elements for the PDF
    elements = []

    # Add heading and subheadings
    heading = Paragraph("Time Entries Report", heading_style)

    # Subheadings for totals
    billable_duration_subheading = Paragraph(f"Total Billable Duration: {total_billable_duration_str}",
                                             subheading_style)
    non_billable_duration_subheading = Paragraph(f"Total Non-Billable Duration: {total_non_billable_duration_str}",
                                                 subheading_style)
    amount_subheading = Paragraph(f"Total Billable Amount: {total_amount_str}", subheading_style)

    # Add heading, subheadings, and main data table to elements
    elements.append(heading)
    elements.append(billable_duration_subheading)
    elements.append(non_billable_duration_subheading)
    elements.append(amount_subheading)
    elements.append(Paragraph("\n", normal_style))  # Add space between subheadings and the main table
    elements.append(Paragraph("\n", normal_style))  # Additional space for better readability
    elements.append(Paragraph("Time Entries", heading_style))
    elements.append(table)

    # Build the PDF
    doc.build(elements)

    # Move to the beginning of the StringIO buffer
    buffer.seek(0)

    # Create a response object with the PDF data
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=time_entries_report.pdf'

    return response


    # Render the HTML template
    # rendered_html = render_template('time_entries_pdf.html', data=data,
    #                                 total_billable_duration_str=total_billable_duration_str,
    #                                 total_non_billable_duration_str=total_non_billable_duration_str,
    #                                 total_amount_str=total_amount_str)
    #
    # # Generate PDF from the rendered HTML
    # pdf = pdfkit.from_string(rendered_html, False, configuration=config)
    #
    # # Create a response with the PDF as an attachment
    # response = make_response(pdf)
    # response.headers['Content-Type'] = 'application/pdf'
    # response.headers['Content-Disposition'] = 'attachment; filename=time_entries.pdf'
    #
    # return response
