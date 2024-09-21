from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

class Admin(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    photo = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    comments = db.relationship('Comment', backref='submission', lazy=True, cascade='all, delete-orphan')
    status = db.Column(db.String(20), default='active')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)

class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)

    @classmethod
    def get_value(cls, key, default=''):
        content = cls.query.filter_by(key=key).first()
        return content.value if content else default

    @classmethod
    def set_value(cls, key, value):
        content = cls.query.filter_by(key=key).first()
        if content:
            content.value = value
        else:
            content = cls(key=key, value=value)
            db.session.add(content)
