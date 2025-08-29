
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    sent_tickets = db.relationship('Ticket', foreign_keys='Ticket.sender_id', backref='sender', lazy=True)
    received_tickets = db.relationship('Ticket', foreign_keys='Ticket.receiver_id', backref='receiver', lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Status(db.Model):
    __tablename__ = "statuses"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(100), unique=True, nullable=False)
    order_index = db.Column(db.Integer, default=0)

class Ticket(db.Model):
    __tablename__ = "tickets"
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    subject = db.Column(db.String(255), nullable=False)
    evaluation = db.Column(db.String(50), nullable=True)
    revenue = db.Column(db.Float, nullable=True)
    comment = db.Column(db.Text, nullable=True)

    status = db.relationship('Status', backref='tickets', lazy=True)

    @property
    def age_days(self):
        end = self.closed_at if self.closed_at else datetime.utcnow()
        return (end - self.created_at).days
