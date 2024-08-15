from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user

from helping_functions import admin_required
from models import Project, db, Client, ProjectConsultant, Consultant

projects_blueprint = Blueprint('projects', __name__)


@projects_blueprint.route('/')
@projects_blueprint.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_projects(id=None):
    if id is not None:
        if not current_user.is_admin:
            logout_user()
            flash("You cannot access that page.")
            return redirect(url_for('login'))

    status = request.args.get('status')
    if current_user.is_admin:
        if not status or status == 'Active':
            projects = Project.query.filter_by(active=True).all()
        else:
            projects = Project.query.filter_by(active=False).all()

        projects = sorted(projects, key=lambda x: x.id)

    else:
        consultants = ProjectConsultant.query.filter_by(consultant_id=current_user.consultant_id).all()
        projects = []
        for consultant in consultants:
            project = Project.query.get(consultant.project_id)
            if not status or status == 'Active':
                if project.active:
                    projects.append(project)
            else:
                if not project.active:
                    projects.append(project)
        projects = sorted(projects, key=lambda x: x.id)

    clients = Client.query.all()
    project = Project.query.get(id)
    if id is not None:
        if project is None:
            flash('Project not found with this id.', 'danger')
            return redirect(url_for('projects.manage_projects'))
        else:
            if request.method == 'POST':
                if not project:
                    project = Project()
                name = request.form.get('name')
                # start_date = request.form.get('start')
                end_date = request.form.get('end_date')
                if not name or not end_date:
                    flash('Please Enter Valid Details.', 'danger')
                    return render_template('index.html', page='view-projects', projects=projects, id=id,
                                           clients=clients)
                if project.price:
                    price = request.form.get('price')
                    if not price:
                        flash('Please Enter Valid Details.', 'danger')
                        return render_template('index.html', page='view-projects', projects=projects, id=id, clients=clients, status=status)
                    project.price = price
                project.name = name
                # project.start_date = start_date
                project.end_date = end_date
                db.session.add(project)
                db.session.commit()
                return redirect(url_for('projects.manage_projects'))

    return render_template('index.html', page='view-projects', projects=projects, id=id, clients=clients, status=status)


@projects_blueprint.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_project():
    project = None
    clients = Client.query.all()
    if request.method == 'POST':
        project = Project()
        project.name = request.form.get('name')
        project.customer_id = request.form.get('client')
        project.start_date = request.form.get('start_date')
        project.end_date = request.form.get('end_date')

        if not project.customer_id or not project.start_date or not project.end_date or not project.name:
            flash('All fields are required', 'danger')
            return render_template('index.html', page='add_project', project=project, clients=clients)

        hourly = request.form.get('hourly')
        if not hourly:
            project.price = request.form.get('price')
            if not project.price:
                flash('No Price input given.', 'danger')
                return render_template('index.html', page='add_project', project=project, clients=clients)

        db.session.add(project)
        db.session.commit()

        # Making the user who added it to be the consultant of that project:
        project_consultant = ProjectConsultant(project_id=project.id, consultant_id=current_user.consultant_id)
        if hourly:
            project_consultant.hourly = True
        else:
            project_consultant.price = project.price

        client = Client.query.get(project.customer_id)
        project_consultant.currency = client.currency

        db.session.add(project_consultant)
        db.session.commit()

        return redirect(url_for('projects.manage_projects'))
    return render_template('index.html', page='add_project', project=project, clients=clients)


@projects_blueprint.route('/delete/<int:id>', methods=['GET'])
@login_required
@admin_required
def delete_project(id):
    project = Project.query.get(id)
    projects_consultants = ProjectConsultant.query.filter_by(project_id=id).all()
    if not projects_consultants:
        db.session.delete(project)
        db.session.commit()
        return redirect(url_for('projects.manage_projects'))
    else:
        flash('This Project has Consultants associated with it. Cannot delete directly.', 'danger')
        return redirect(url_for('projects.manage_projects'))


@projects_blueprint.route('/projects-consultants')
@projects_blueprint.route('edit-project-consultant/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def projects_consultants(id=None):
    if request.method == 'POST':
        currency = request.form.get('currency')
        price = request.form.get('price')
        if not price or not currency:
            flash('Price and Currency are required', 'danger')
            return redirect(url_for('projects.projects_consultants'))
        project_consultant_object = ProjectConsultant.query.get(id)
        if not project_consultant_object:
            flash('Something went wrong. No matching record found in the database.')
            return redirect(url_for('projects.projects_consultants'))
        project_consultant_object.price = price
        project_consultant_object.currency = currency
        db.session.add(project_consultant_object)
        db.session.commit()
        return redirect(url_for('projects.projects_consultants'))

    status = request.args.get('status')
    if current_user.is_admin:
        if not status or status == 'Active':
            projects = Project.query.filter_by(active=True).all()
        else:
            projects = Project.query.filter_by(active=False).all()

        projects = sorted(projects, key=lambda x: x.id)
    else:
        flash('You are not authorized to access this page.', 'danger')
        return redirect(url_for('app.login'))
    # projects = Project.query.all()
    clients = Client.query.all()
    projects_with_consultants = []
    for project in projects:
        consultants = []
        project_consultants = ProjectConsultant.query.filter_by(project_id=project.id).all()
        for project_consultant in project_consultants:
            consultant = Consultant.query.get(project_consultant.consultant_id)
            consultants.append({'consultant': consultant, 'project_consultant': project_consultant})
        projects_with_consultants.append({'project': project, 'consultants': consultants})
    return render_template('index.html', page='projects-consultants', projects=projects_with_consultants, clients=clients, id=id)

@projects_blueprint.route('/assign-consultants/<int:project_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def assign_consultants(project_id):
    project = Project.query.get(project_id)
    if not project:
        flash('Project not found with this id.', 'danger')
        return redirect(url_for('projects.projects_consultants'))
    if request.method == 'POST':
        assigned_consultant = request.form.get('consultant')
        currency = request.form.get('currency')
        price = request.form.get('price')
        hourly = request.form.get('hourly')
        if not assigned_consultant or not price:
            flash('All fields are required', 'danger')
            return redirect(url_for('projects.assign_consultants', project_id=project_id))

        project_consultant_new = ProjectConsultant(consultant_id=assigned_consultant, project_id=project_id, price=price, currency=currency)
        if hourly:
            project_consultant_new.hourly = True
        db.session.add(project_consultant_new)
        db.session.commit()
        return redirect(url_for('projects.projects_consultants'))

    assigned_consultants = []
    project_consultants = ProjectConsultant.query.filter_by(project_id=project.id).all()
    for project_consultant in project_consultants:
        consultant = Consultant.query.get(project_consultant.consultant_id)
        assigned_consultants.append(consultant)

    all_consultants = Consultant.query.all()

    unassigned_consultants = [consultant for consultant in all_consultants if consultant not in assigned_consultants]
    print(unassigned_consultants)
    return render_template('index.html', page='assign-consultants', consultants=unassigned_consultants, project=project)


@projects_blueprint.route('delete-project-consultant/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def delete_project_consultant(id):
    project_consultant = ProjectConsultant.query.get(id)
    if not project_consultant:
        flash('No consultant and project found with the given details.')
    else:
        db.session.delete(project_consultant)
        db.session.commit()
        flash('Consultant deleted successfully!', 'success')
    return redirect(url_for('projects.projects_consultants'))


@projects_blueprint.route('/activate', methods=['POST'])
@login_required
@admin_required
def activate():
    id = request.form.get('id', None)
    if not id:
        flash('No project id provided.', 'danger')
        return redirect(url_for('projects.manage_projects'))
    project = Project.query.get(id)
    if not project:
        flash('Project not found with this id.', 'danger')
        return redirect(url_for('projects.manage_projects'))
    project.active = True
    db.session.add(project)
    db.session.commit()
    flash('Project activated.', 'success')
    return redirect(url_for('projects.manage_projects'))


@projects_blueprint.route('/archive', methods=['POST'])
@login_required
@admin_required
def archive():
    id = request.form.get('id', None)
    if not id:
        flash('No project id provided.', 'danger')
        return redirect(url_for('projects.manage_projects'))

    project = Project.query.get(id)
    if not project:
        flash('Project not found with this id.', 'danger')
        return redirect(url_for('projects.manage_projects'))
    project.active = False
    db.session.add(project)
    db.session.commit()
    flash('Project archived.', 'success')
    return redirect(url_for('projects.manage_projects', status='Archived'))



