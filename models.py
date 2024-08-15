from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})

db = SQLAlchemy()

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    address = db.Column(db.String(200))
    country = db.Column(db.String(100))
    currency = db.Column(db.String(10))

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('client.id', ondelete='CASCADE'), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    name = db.Column(db.String(200))
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    price = db.Column(db.Float, nullable=True)
    consultants = db.relationship('ProjectConsultant', back_populates='project')

class ProjectConsultant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)
    consultant_id = db.Column(db.Integer, db.ForeignKey('consultant.id', ondelete='CASCADE'), nullable=False)
    hourly = db.Column(db.Boolean, default=False)
    price = db.Column(db.Float)
    currency = db.Column(db.String(10))
    paid = db.Column(db.Boolean, default=False)
    remaining_price = db.Column(db.Float)

    project = db.relationship('Project', back_populates='consultants')
    consultant = db.relationship('Consultant', back_populates='projects')

class Consultant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    address = db.Column(db.String(200))
    country = db.Column(db.String(100))
    projects = db.relationship('ProjectConsultant', back_populates='consultant')

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    password = db.Column(db.Text)
    consultant_id = db.Column(db.Integer, db.ForeignKey('consultant.id', ondelete='CASCADE'), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    password_set = db.Column(db.Boolean, default=False)


class TimeEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_consultant_id = db.Column(db.Integer, db.ForeignKey('project_consultant.id', ondelete='CASCADE'), nullable=False)
    hours = db.Column(db.Integer)
    minutes = db.Column(db.Integer)
    performance_date = db.Column(db.Date)
    description = db.Column(db.Text)
    invoiced = db.Column(db.Boolean, default=False)
    billable = db.Column(db.Boolean, default=True)
    tracked = db.Column(db.Boolean, default=False)
