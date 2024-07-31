from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from models import Client, db, Project

clients_blueprint = Blueprint('clients', __name__)


@clients_blueprint.route('/')
@clients_blueprint.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def manage_clients(id=None):
    clients = Client.query.all()
    client = Client.query.get(id)
    if id is not None:
        if client is None:
            flash('Client not found with this id.', 'danger')
            return redirect(url_for('clients.manage_clients'))
        else:
            if request.method == 'POST':
                if not client:
                    client = Client()
                name = request.form.get('name')
                address = request.form.get('address')
                country = request.form.get('country')
                currency = request.form.get('currency')
                if not address or not country or not currency or not name:
                    flash('All fields are required', 'danger')
                    return render_template('index.html', page='view-clients', clients=clients, id=id)
                client.name = name
                client.address = address
                client.country = country
                client.currency = currency
                db.session.add(client)
                db.session.commit()
                return redirect(url_for('clients.manage_clients'))

    return render_template('index.html', page='view-clients', clients=clients, id=id)
    # return render_template('/client/clients_dashboard.html', clients=clients)


@clients_blueprint.route('/add', methods=['GET', 'POST'])
@login_required
def add_client():
    client = None
    if request.method == 'POST':
        client = Client()
        client.name = request.form.get('name')
        client.address = request.form.get('address')
        client.country = request.form.get('country')
        client.currency = request.form.get('currency')

        if not client.address or not client.country or not client.currency or not client.name:
            flash('All fields are required', 'danger')
            return render_template('index.html', page='add_client', client=client)

        db.session.add(client)
        db.session.commit()
        return redirect(url_for('clients.manage_clients'))
    return render_template('index.html', page='add_client', client=client)


@clients_blueprint.route('/clients/delete/<int:id>', methods=['GET'])
@login_required
def delete_client(id):
    client = Client.query.get(id)
    projects = Project.query.all()
    for project in projects:
        if project.customer_id == id:
            flash("Error deleting Client. Client has project/s associated with them.", "danger")
            return redirect(url_for('manage_clients'))
    db.session.delete(client)
    db.session.commit()
    return redirect(url_for('clients.manage_clients'))


