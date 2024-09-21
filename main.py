from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import SQLAlchemyError
from flask_migrate import Migrate
import os
from datetime import datetime
from models import db, Submission, Comment, Admin, Content
from utils import allowed_file, get_coordinates_from_image

app = Flask(__name__)
app.config.from_object('config.Config')

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

@app.context_processor
def inject_content():
    return dict(Content=Content)

@app.route('/')
def index():
    try:
        page = request.args.get('page', 1, type=int)
        submissions = Submission.query.filter_by(status='active').order_by(Submission.created_at.desc()).paginate(page=page, per_page=6, error_out=False)
        return render_template('index.html', submissions=submissions.items if submissions else [], pagination=submissions)
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error in index route: {str(e)}")
        flash("An error occurred while loading the page. Please try again.")
        return render_template('index.html', submissions=[], pagination=None), 500
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in index route: {str(e)}")
        flash("An error occurred while loading the page. Please try again.")
        return render_template('index.html', submissions=[], pagination=None), 500

@app.route('/comment', methods=['POST'])
def add_comment():
    try:
        submission_id = request.form.get('submission_id')
        content = request.form.get('content')
        
        if not submission_id or not content:
            return jsonify({'error': 'Missing submission_id or content'}), 400
        
        submission = Submission.query.get(submission_id)
        if not submission:
            return jsonify({'error': 'Submission not found'}), 404
        
        new_comment = Comment(content=content, submission_id=submission_id)
        db.session.add(new_comment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Comment added successfully',
            'comment': {
                'id': new_comment.id,
                'content': new_comment.content,
                'created_at': new_comment.created_at.strftime('%Y-%m-%d %I:%M %p')
            }
        }), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error in add_comment: {str(e)}")
        return jsonify({'error': 'An error occurred while adding your comment. Please try again.'}), 500
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in add_comment: {str(e)}")
        return jsonify({'error': 'An error occurred while adding your comment. Please try again.'}), 500

@app.route('/edit_comment/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_comment(id):
    comment = Comment.query.get_or_404(id)
    if request.method == 'POST':
        comment.content = request.form.get('content')
        db.session.commit()
        flash('Comment updated successfully', 'success')
        return redirect(url_for('moderator_submission_detail', id=comment.submission_id))
    return render_template('edit_comment.html', comment=comment)

@app.route('/delete_comment/<int:id>', methods=['GET', 'POST'])
@login_required
def delete_comment(id):
    comment = Comment.query.get_or_404(id)
    submission_id = comment.submission_id
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted successfully', 'success')
    return redirect(url_for('moderator_submission_detail', id=submission_id))

@app.route('/manage_comments/<int:submission_id>')
@login_required
def manage_comments(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    return render_template('manage_comments.html', submission=submission)

@app.route('/about')
def about():
    content = Content.get_value('about_content', '')
    return render_template('about.html', content=content)

@app.route('/donate')
def donate():
    content = Content.get_value('donate_content', '')
    return render_template('donate.html', content=content)

@app.route('/contact')
def contact():
    content = Content.get_value('contact_content', '')
    return render_template('contact.html', content=content)

@app.route('/submission/<int:id>')
def submission_detail(id):
    try:
        submission = Submission.query.get_or_404(id)
        return render_template('detail.html', submission=submission)
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error in submission_detail: {str(e)}")
        flash("An error occurred while loading the submission details. Please try again.")
        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Error in submission_detail: {str(e)}")
        flash("An error occurred while loading the submission details. Please try again.")
        return redirect(url_for('index'))

@app.route('/submit_report', methods=['POST'])
def submit_report():
    try:
        if 'photo' not in request.files:
            flash('No file part')
            return redirect(url_for('index'))
        
        photo = request.files['photo']
        location = request.form.get('location')
        
        if photo.filename == '':
            flash('No selected file')
            return redirect(url_for('index'))
        
        if photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo.save(photo_path)
            
            coordinates = get_coordinates_from_image(photo_path)
            
            new_submission = Submission(photo=filename, location=location)
            db.session.add(new_submission)
            db.session.commit()
            
            flash('Your report has been submitted successfully!')
            return redirect(url_for('index'))
        else:
            flash('Invalid file type')
            return redirect(url_for('index'))
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error in submit_report: {str(e)}")
        flash('An error occurred while submitting your report. Please try again.')
        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Error in submit_report: {str(e)}")
        flash('An error occurred while submitting your report. Please try again.')
        return redirect(url_for('index'))

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
            app.logger.info(f"Successful login attempt for user: {username}")
            return redirect(url_for('moderator'))
        else:
            app.logger.warning(f"Failed login attempt for user: {username}")
            flash('Invalid username or password')
    return render_template('login.html')

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
        db.session.rollback()
        app.logger.error(f"Database error in moderator view: {str(e)}")
        flash("An error occurred while loading the moderator dashboard. Please try again.")
        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Error in moderator view: {str(e)}")
        flash("An error occurred while loading the moderator dashboard. Please try again.")
        return redirect(url_for('index'))

@app.route('/moderator/submission/<int:id>')
@login_required
def moderator_submission_detail(id):
    try:
        submission = Submission.query.get_or_404(id)
        return render_template('moderator_detail.html', submission=submission)
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error in moderator_submission_detail: {str(e)}")
        flash("An error occurred while loading the submission details. Please try again.")
        return redirect(url_for('moderator'))
    except Exception as e:
        app.logger.error(f"Error in moderator_submission_detail: {str(e)}")
        flash("An error occurred while loading the submission details. Please try again.")
        return redirect(url_for('moderator'))

@app.route('/change_status/<int:id>/<string:status>')
@login_required
def change_status(id, status):
    try:
        submission = Submission.query.get_or_404(id)
        submission.status = status
        db.session.commit()
        flash(f'Submission {id} status changed to {status}')
        return redirect(url_for('moderator'))
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error in change_status: {str(e)}")
        flash("An error occurred while changing the submission status. Please try again.")
        return redirect(url_for('moderator'))
    except Exception as e:
        app.logger.error(f"Error in change_status: {str(e)}")
        flash("An error occurred while changing the submission status. Please try again.")
        return redirect(url_for('moderator'))

@app.route('/delete_submission/<int:id>')
@login_required
def delete_submission(id):
    try:
        submission = Submission.query.get_or_404(id)
        db.session.delete(submission)
        db.session.commit()
        flash(f'Submission {id} has been deleted')
        return redirect(url_for('moderator'))
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error in delete_submission: {str(e)}")
        flash("An error occurred while deleting the submission. Please try again.")
        return redirect(url_for('moderator'))
    except Exception as e:
        app.logger.error(f"Error in delete_submission: {str(e)}")
        flash("An error occurred while deleting the submission. Please try again.")
        return redirect(url_for('moderator'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin/content', methods=['GET', 'POST'])
@login_required
def admin_content():
    if request.method == 'POST':
        try:
            Content.set_value('site_name', request.form.get('site_name'))
            Content.set_value('about_content', request.form.get('about_content'))
            Content.set_value('donate_content', request.form.get('donate_content'))
            Content.set_value('contact_content', request.form.get('contact_content'))
            db.session.commit()
            flash('Content updated successfully', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating content: {str(e)}")
            flash('An error occurred while updating the content. Please try again.', 'error')
        return redirect(url_for('admin_content'))
    
    site_name = Content.get_value('site_name', 'Colorado Citizens Project - Report Damaged Road')
    about_content = Content.get_value('about_content', '')
    donate_content = Content.get_value('donate_content', '')
    contact_content = Content.get_value('contact_content', '')
    
    return render_template('admin_content.html', 
                           site_name=site_name, 
                           about_content=about_content, 
                           donate_content=donate_content, 
                           contact_content=contact_content)

@app.route('/admin/users')
@login_required
def admin_users():
    users = Admin.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
def add_admin_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username and password:
            new_user = Admin(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('New admin user added successfully', 'success')
            return redirect(url_for('admin_users'))
        else:
            flash('Username and password are required', 'error')
    return render_template('admin_user_form.html', user=None)

@app.route('/admin/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_admin_user(id):
    user = Admin.query.get_or_404(id)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username:
            user.username = username
            if password:
                user.set_password(password)
            db.session.commit()
            flash('Admin user updated successfully', 'success')
            return redirect(url_for('admin_users'))
        else:
            flash('Username is required', 'error')
    return render_template('admin_user_form.html', user=user)

@app.route('/admin/users/delete/<int:id>', methods=['POST'])
@login_required
def delete_admin_user(id):
    user = Admin.query.get_or_404(id)
    if user.id != current_user.id:
        db.session.delete(user)
        db.session.commit()
        flash('Admin user deleted successfully', 'success')
    else:
        flash('You cannot delete your own account', 'error')
    return redirect(url_for('admin_users'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
