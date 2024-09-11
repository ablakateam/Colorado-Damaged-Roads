import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from models import db, Submission, Comment, Admin
from config import Config
from utils import allowed_file, get_coordinates_from_image
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)
app.config.from_object(Config)

def setup_logging(app):
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/colorado_citizens_project.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Colorado Citizens Project startup')

setup_logging(app)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Create upload folder if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@app.before_request
def before_request():
    try:
        # Remove the db.session.ping() call
        pass
    except SQLAlchemyError:
        db.session.rollback()

with app.app_context():
    try:
        db.create_all()
        db.session.commit()  # Added this line to update the database schema
        # Create admin user if not exists
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            admin = Admin(username='admin')
            admin.set_password('admin')
            db.session.add(admin)
        else:
            admin.set_password('admin')
        db.session.commit()
    except SQLAlchemyError as e:
        app.logger.error(f"Error initializing database: {str(e)}")

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('moderator'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = Admin.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            app.logger.info(f"User {username} logged in successfully")
            return redirect(url_for('moderator'))
        else:
            app.logger.warning(f"Failed login attempt for user {username}")
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/moderator')
@login_required
def moderator():
    try:
        page = request.args.get('page', 1, type=int)
        status_filter = request.args.get('status', 'all')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')

        query = Submission.query

        if status_filter != 'all':
            query = query.filter_by(status=status_filter)

        if sort_by == 'created_at':
            query = query.order_by(Submission.created_at.desc() if sort_order == 'desc' else Submission.created_at.asc())
        elif sort_by == 'location':
            query = query.order_by(Submission.location.desc() if sort_order == 'desc' else Submission.location.asc())
        elif sort_by == 'comments':
            query = query.outerjoin(Comment).group_by(Submission.id).order_by(db.func.count(Comment.id).desc() if sort_order == 'desc' else db.func.count(Comment.id).asc())

        pagination = query.paginate(page=page, per_page=10, error_out=False)
        submissions = pagination.items

        # Add statistics
        total_submissions = Submission.query.count()
        active_submissions = Submission.query.filter_by(status='active').count()
        on_hold_submissions = Submission.query.filter_by(status='on_hold').count()
        total_comments = Comment.query.count()

        return render_template('moderator.html', 
                               submissions=submissions, 
                               pagination=pagination, 
                               status_filter=status_filter, 
                               sort_by=sort_by, 
                               sort_order=sort_order,
                               total_submissions=total_submissions,
                               active_submissions=active_submissions,
                               on_hold_submissions=on_hold_submissions,
                               total_comments=total_comments)
    except SQLAlchemyError as e:
        app.logger.error(f"Error loading submissions in moderator view: {str(e)}")
        flash(f"Error loading submissions: {str(e)}")
        return redirect(url_for('index'))

# ... (keep the rest of the routes unchanged)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 80))
    app.run(host='0.0.0.0', port=port)
