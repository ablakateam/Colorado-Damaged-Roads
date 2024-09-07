import os
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
        # Create admin user if not exists
        if not Admin.query.filter_by(username='admin').first():
            admin = Admin(username='admin')
            admin.set_password('p@ssword')
            db.session.add(admin)
            db.session.commit()
    except SQLAlchemyError as e:
        print(f"Error initializing database: {str(e)}")

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
            next_page = request.args.get('next')
            return redirect(next_page or url_for('moderator'))
        else:
            flash('Wrong credentials')
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
        flash(f"Error loading submissions: {str(e)}")
        return redirect(url_for('index'))

@app.route('/')
def index():
    """Colorado Citizens Project - Report Damaged Road: Main page"""
    try:
        page = request.args.get('page', 1, type=int)
        pagination = Submission.query.order_by(Submission.created_at.desc()).paginate(page=page, per_page=6, error_out=False)
        submissions = pagination.items
        return render_template('index.html', submissions=submissions, pagination=pagination)
    except SQLAlchemyError as e:
        flash(f"Error loading submissions: {str(e)}")
        return render_template('index.html', submissions=[], pagination=None)

@app.route('/submit', methods=['POST'])
def submit():
    """Submit a new road damage report"""
    if 'photo' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        location = request.form.get('location')
        if not location:
            coordinates = get_coordinates_from_image(filepath)
            location = f"{coordinates['latitude']}, {coordinates['longitude']}" if coordinates else "Unknown"
        
        try:
            new_submission = Submission(photo=filename, location=location)
            db.session.add(new_submission)
            db.session.commit()
            return jsonify({'success': True, 'id': new_submission.id}), 201
        except SQLAlchemyError as e:
            db.session.rollback()
            return jsonify({'error': f'Database error: {str(e)}'}), 500
    
    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/submission/<int:id>')
def submission_detail(id):
    """View details of a specific road damage report"""
    try:
        submission = Submission.query.get_or_404(id)
        return render_template('detail.html', submission=submission)
    except SQLAlchemyError as e:
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
        return jsonify({'success': True, 'id': new_comment.id}), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/donate')
def donate():
    return render_template('donate.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
