from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime

from models import db, User, Video, Like, Comment, Follow
public_pages = ['login', 'register', 'index']
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "database", "social.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    print("✅ تم إنشاء قاعدة البيانات بنجاح!")

@app.route('/')
def index():
    videos = Video.query.order_by(Video.created_at.desc()).all()
    return render_template('index.html', videos=videos)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود مسبقاً')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('تم إنشاء الحساب بنجاح! سجل دخولك الآن')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        
        if 'video' not in request.files:
            flash('لم يتم اختيار فيديو')
            return redirect(request.url)
        
        file = request.files['video']
        if file.filename == '':
            flash('لم يتم اختيار فيديو')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            new_video = Video(
                title=title,
                description=description,
                filename=filename,
                user_id=current_user.id
            )
            db.session.add(new_video)
            db.session.commit()
            
            flash('تم رفع الفيديو بنجاح!')
            return redirect(url_for('index'))
        else:
            flash('امتداد الملف غير مسموح. استخدم mp4, mov, avi, mkv')
    
    return render_template('upload.html')

@app.route('/video/<int:video_id>')
def video(video_id):
    video = Video.query.get_or_404(video_id)
    video.views += 1
    db.session.commit()
    return render_template('video.html', video=video)

@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    videos = Video.query.filter_by(user_id=user.id).order_by(Video.created_at.desc()).all()
    return render_template('profile.html', user=user, videos=videos)

@app.route('/like/<int:video_id>')
@login_required
def like(video_id):
    video = Video.query.get_or_404(video_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, video_id=video_id).first()
    
    if existing_like:
        db.session.delete(existing_like)
    else:
        new_like = Like(user_id=current_user.id, video_id=video_id)
        db.session.add(new_like)
    
    db.session.commit()
    return redirect(url_for('video', video_id=video_id))

@app.route('/comment/<int:video_id>', methods=['POST'])
@login_required
def comment(video_id):
    content = request.form['content']
    if content.strip():
        new_comment = Comment(content=content, user_id=current_user.id, video_id=video_id)
        db.session.add(new_comment)
        db.session.commit()
    return redirect(url_for('video', video_id=video_id))

@app.route('/follow/<username>')
@login_required
def follow(username):
    user_to_follow = User.query.filter_by(username=username).first_or_404()
    
    if user_to_follow == current_user:
        flash('لا يمكنك متابعة نفسك')
        return redirect(url_for('profile', username=username))
    
    existing_follow = Follow.query.filter_by(
        follower_id=current_user.id, 
        followed_id=user_to_follow.id
    ).first()
    
    if existing_follow:
        db.session.delete(existing_follow)
        flash(f'تم إلغاء متابعة {username}')
    else:
        new_follow = Follow(follower_id=current_user.id, followed_id=user_to_follow.id)
        db.session.add(new_follow)
        flash(f'أنت الآن تتابع {username}')
    
    db.session.commit()
    return redirect(url_for('profile', username=username))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
@app.route('/explore')
def explore():
    videos = Video.query.order_by(Video.views.desc()).all()
    return render_template('index.html', videos=videos)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
