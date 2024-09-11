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
import shutil

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
        pass
    except SQLAlchemyError:
        db.session.rollback()

def create_sample_submission():
    sample_image = 'Screenshot_2024-09-06_115912.png'
    source_path = os.path.abspath(os.path.join(app.root_path, sample_image))
    destination_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], sample_image))
    
    app.logger.info(f"Attempting to create sample submission")
    app.logger.info(f"Source path: {source_path}")
    app.logger.info(f"Destination path: {destination_path}")
    
    if os.path.exists(source_path):
        shutil.copy(source_path, destination_path)
        app.logger.info(f"Sample image copied from {source_path} to {destination_path}")
        
        sample_submission = Submission(
            photo=sample_image,
            location='Sample Location, Colorado',
            created_at=datetime.utcnow(),
            status='active'
        )
        db.session.add(sample_submission)
        db.session.commit()
        app.logger.info(f'Sample submission created with image: {destination_path}')
    else:
        app.logger.warning(f'Sample image not found: {source_path}')

with app.app_context():
    try:
        db.create_all()
        db.session.commit()
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            admin = Admin(username='admin')
            admin.set_password('admin')
            db.session.add(admin)
        else:
            admin.set_password('admin')
        db.session.commit()
        
        if Submission.query.count() == 0:
            create_sample_submission()
        
        sample_image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'Screenshot_2024-09-06_115912.png')
        if os.path.exists(sample_image_path):
            app.logger.info(f"Sample image exists at: {sample_image_path}")
        else:
            app.logger.warning(f"Sample image not found at: {sample_image_path}")
        
    except SQLAlchemyError as e:
        app.logger.error(f"Error initializing database: {str(e)}")

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

@app.route('/')
def index():
    try:
        page = request.args.get('page', 1, type=int)
        submissions = Submission.query.filter_by(status='active').order_by(Submission.created_at.desc()).paginate(page=page, per_page=6, error_out=False)
        app.logger.info(f"Index route accessed. Total submissions: {submissions.total}")
        app.logger.info(f"Submissions on this page: {len(submissions.items)}")
        for submission in submissions.items:
            app.logger.info(f"Submission ID: {submission.id}, Photo: {submission.photo}, Location: {submission.location}")
        return render_template('index.html', submissions=submissions.items, pagination=submissions)
    except Exception as e:
        app.logger.error(f"Error in index route: {str(e)}")
        flash("An error occurred while loading the page. Please try again.")
        return render_template('index.html', submissions=[], pagination=None), 500

@app.route('/submit', methods=['POST'])
def submit_report():
    try:
        if 'photo' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['photo']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            file.save(file_path)
            app.logger.info(f"File saved successfully: {file_path}")
            
            location = request.form.get('location')
            new_submission = Submission(photo=filename, location=location)
            db.session.add(new_submission)
            db.session.commit()
            app.logger.info(f"New submission added to database: ID {new_submission.id}")
            
            return jsonify({
                'success': True,
                'message': 'Your report has been submitted successfully!',
                'submission': {
                    'id': new_submission.id,
                    'photo': filename,
                    'location': location,
                    'created_at': new_submission.created_at.strftime('%Y-%m-%d %I:%M %p')
                }
            }), 200
        else:
            return jsonify({'error': 'Invalid file type'}), 400
    except Exception as e:
        app.logger.error(f"Error in submit_report: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'An error occurred while submitting your report. Please try again.'}), 500

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/donate')
def donate():
    return render_template('donate.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

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

@app.route('/moderator/submission/<int:id>')
@login_required
def moderator_submission_detail(id):
    submission = Submission.query.get_or_404(id)
    return render_template('moderator_detail.html', submission=submission)

@app.route('/change_status/<int:id>/<string:status>')
@login_required
def change_status(id, status):
    submission = Submission.query.get_or_404(id)
    submission.status = status
    db.session.commit()
    flash(f'Submission {id} status changed to {status}')
    return redirect(url_for('moderator'))

@app.route('/delete_submission/<int:id>')
@login_required
def delete_submission(id):
    submission = Submission.query.get_or_404(id)
    db.session.delete(submission)
    db.session.commit()
    flash(f'Submission {id} has been deleted')
    return redirect(url_for('moderator'))

@app.route('/submission/<int:id>')
def submission_detail(id):
    submission = Submission.query.get_or_404(id)
    return render_template('detail.html', submission=submission)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
