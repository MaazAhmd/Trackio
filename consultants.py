from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from helping_functions import admin_required
from models import Consultant, db, User

consultants_blueprint = Blueprint('consultants', __name__)


@consultants_blueprint.route('/')
@consultants_blueprint.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def manage_consultants(id=None):
    consultants = Consultant.query.all()
    consultant = Consultant.query.get(id)
    if id is not None:
        if consultant is None:
            flash('Consultant not found with this id.', 'danger')
            return redirect(url_for('consultants.manage_consultants'))
        else:
            if request.method == 'POST':
                if not consultant:
                    consultant = Consultant()
                name = request.form.get('name')
                address = request.form.get('address')
                country = request.form.get('country')
                if not address or not country or not name:
                    flash('All fields are required', 'danger')
                    return render_template('index.html', page='view-consultants', consultants=consultants, id=id)
                consultant.name = name
                consultant.address = address
                consultant.country = country
                db.session.add(consultant)
                db.session.commit()
                return redirect(url_for('consultants.manage_consultants'))

    return render_template('index.html', page='view-consultants', consultants=consultants, id=id)


@consultants_blueprint.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_consultant():
    consultant = None
    new_user = None
    if request.method == 'POST':
        username = request.form.get('username')
        user = User.query.filter_by(username=username).first()
        consultant = Consultant()
        consultant.name = request.form.get('name')
        consultant.address = request.form.get('address')
        consultant.country = request.form.get('country')

        if user:
            flash('User already exists with this Username', 'danger')
            return render_template('index.html', page='add_consultant', consultant=consultant)

        if not consultant.address or not consultant.country or not consultant.name or not username:
            flash('All fields are required', 'danger')
            return render_template('index.html', page='add_consultant', consultant=consultant)

        try:
            db.session.add(consultant)
            db.session.commit()

            new_user = User(username=username, consultant_id=consultant.id)
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            flash('Something went wrong.', 'danger')
            db.session.rollback()

        return redirect(url_for('consultants.manage_consultants'))
    return render_template('index.html', page='add_consultant', consultant=consultant)


@consultants_blueprint.route('/consultants/delete/<int:id>', methods=['GET'])
@login_required
@admin_required
def delete_consultant(id):
    consultant = Consultant.query.get(id)
    db.session.delete(consultant)
    db.session.commit()
    return redirect(url_for('consultants.manage_consultants'))
