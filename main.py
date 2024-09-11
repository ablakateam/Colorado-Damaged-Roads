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
        submissions = Submission.query.order_by(Submission.created_at.desc()).all()
        return render_template('moderator.html', submissions=submissions)
    except SQLAlchemyError as e:
        app.logger.error(f"Error loading submissions in moderator view: {str(e)}")
        flash(f"Error loading submissions: {str(e)}")
        return redirect(url_for('index'))

@app.route('/')
def index():
    """Colorado Citizens Project - Report Damaged Road: Main page"""
    try:
        page = request.args.get('page', 1, type=int)
        pagination = Submission.query.filter_by(status='active').order_by(Submission.created_at.desc()).paginate(page=page, per_page=6, error_out=False)
        submissions = pagination.items
        return render_template('index.html', submissions=submissions, pagination=pagination)
    except Exception as e:
        app.logger.error(f"Error in index route: {str(e)}")
        flash("An error occurred while loading the page. Please try again.")
        return render_template('index.html', submissions=[], pagination=None), 500

@app.route('/submit', methods=['POST'])
def submit():
    """Submit a new road damage report"""
    if 'photo' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            location = request.form.get('location')
            if not location:
                coordinates = get_coordinates_from_image(filepath)
                location = f"{coordinates['latitude']}, {coordinates['longitude']}" if coordinates else "Unknown"
            
            new_submission = Submission(photo=filename, location=location)
            db.session.add(new_submission)
            db.session.commit()
            app.logger.info(f"New submission created: ID {new_submission.id}")
            return jsonify({'success': True, 'id': new_submission.id}), 201
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error creating new submission: {str(e)}")
            return jsonify({'error': f'An error occurred while processing your submission: {str(e)}'}), 500
    
    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/submission/<int:id>')
def submission_detail(id):
    """View details of a specific road damage report"""
    try:
        submission = Submission.query.get_or_404(id)
        return render_template('detail.html', submission=submission)
    except Exception as e:
        app.logger.error(f"Error loading submission details for ID {id}: {str(e)}")
        flash(f"Error loading submission: {str(e)}")
        return redirect(url_for('index'))

@app.route('/comment', methods=['POST'])
def add_comment():
    """Add a comment to a road damage report"""
    submission_id = request.form.get('submission_id')
    content = request.form.get('content')
    
    if not submission_id or not content:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        new_comment = Comment(submission_id=submission_id, content=content)
        db.session.add(new_comment)
        db.session.commit()
        app.logger.info(f"New comment added to submission ID {submission_id}")
        return jsonify({'success': True, 'id': new_comment.id}), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error adding comment to submission ID {submission_id}: {str(e)}")
        return jsonify({'error': f'An error occurred while adding your comment: {str(e)}'}), 500

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/donate')
def donate():
    return render_template('donate.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/change_status/<int:id>/<string:status>')
@login_required
def change_status(id, status):
    try:
        submission = Submission.query.get_or_404(id)
        submission.status = status
        db.session.commit()
        app.logger.info(f"Submission {id} status changed to {status}")
        flash(f'Submission {id} status changed to {status}')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error changing status of submission {id}: {str(e)}")
        flash(f"Error changing submission status: {str(e)}")
    return redirect(url_for('moderator'))

@app.route('/delete_submission/<int:id>')
@login_required
def delete_submission(id):
    try:
        submission = Submission.query.get_or_404(id)
        db.session.delete(submission)
        db.session.commit()
        app.logger.info(f"Submission {id} has been deleted")
        flash(f'Submission {id} has been deleted')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting submission {id}: {str(e)}")
        flash(f"Error deleting submission: {str(e)}")
    return redirect(url_for('moderator'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
