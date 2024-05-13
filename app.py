from flask import Flask, request, redirect, render_template, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///festival.db'
app.config['SECRET_KEY'] = '123456789'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads/'  # Dossier où les fichiers seront enregistrés
app.config['ALLOWED_EXTENSIONS'] = {'mp3'}  # Types de fichiers autorisés
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128))  # Store plaintext passwords
    phone = db.Column(db.String(20), nullable=True)
    profile_picture = db.Column(db.String(255), nullable=True)
    crew_id = db.Column(db.Integer, db.ForeignKey('crew.id'), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Crew(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    photo = db.Column(db.String(255), nullable=True)
    mp3_file = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    members = db.relationship('User', backref='crew', lazy=True)  # Ajout de la relation


class SearchMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    user = db.relationship('User', backref='search_messages')



@app.route('/signup', methods=['GET', 'POST'])
def signup():
    crews = Crew.query.all()
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        crew_choice = request.form['crew']
        redirect_after_signup = request.form['redirect_after_signup']

        user_by_email = User.query.filter_by(email=email).first()
        user_by_username = User.query.filter_by(username=username).first()

        if user_by_email or user_by_username:
            flash('Un compte avec cet email ou ce nom d’utilisateur existe déjà.', 'error')
            return render_template('signup.html', crews=crews)

        new_user = User(username=username, email=email, password=password)

        if crew_choice.isdigit():  # Vérifie si l'utilisateur a sélectionné un équipage existant
            new_user.crew_id = int(crew_choice)  # Affecte l'utilisateur à l'équipage sélectionné

        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)

        if redirect_after_signup == 'create_crew':
            return redirect(url_for('create_crew'))
        elif redirect_after_signup == 'search_crew':
            return redirect(url_for('search_crew'))
        
        return redirect(url_for('index'))

    return render_template('signup.html', crews=crews)




@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Échec de la connexion. Veuillez vérifier vos identifiants ou créer un compte.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))



@app.route('/create_crew', methods=['GET', 'POST'])
@login_required
def create_crew():
    if request.method == 'POST':
        name = request.form['name']
        photo = request.form['photo']  # Gère toujours la photo comme URL pour l'instant
        description = request.form['description']
        file = request.files['mp3_file']

        if file and allowed_file(file.filename):
            file_path = secure_filename(file.filename)  # Juste le nom du fichier sécurisé, sans le chemin
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], file_path))  # Sauvegarde avec le chemin complet

            # Créez l'instance de Crew ici avant d'assigner mp3_file
            new_crew = Crew(name=name, photo=photo, description=description, mp3_file=file_path)
            db.session.add(new_crew)
            db.session.commit()

            # Ajouter l'utilisateur courant comme membre de l'équipage
            current_user.crew_id = new_crew.id
            db.session.commit()

            flash('Équipage créé avec succès!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Type de fichier non autorisé. Seuls les fichiers MP3 sont acceptés.', 'error')

    return render_template('create_crew.html')



@app.route('/join_crew/<int:crew_id>', methods=['GET', 'POST'])
def join_crew(crew_id):
    # Ici, on suppose que l'utilisateur est déjà connecté et que son ID est disponible
    user = User.query.filter_by(id=session['user_id']).first()  # Assure-toi que l'ID utilisateur est bien en session
    crew = Crew.query.filter_by(id=crew_id).first()
    if request.method == 'POST':
        user.crew_id = crew_id  
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('join_crew.html', crew=crew)

@app.route('/search_crew', methods=['GET', 'POST'])
@login_required
def search_crew():
    if request.method == 'POST':
        message = request.form['message']
        new_search = SearchMessage(user_id=current_user.id, message=message)
        db.session.add(new_search)
        db.session.commit()
        return redirect(url_for('search_crew'))
    search_messages = SearchMessage.query.all()
    return render_template('search_crew.html', search_messages=search_messages)


@app.route('/edit_crew/<int:crew_id>', methods=['GET', 'POST'])
@login_required
def edit_crew(crew_id):
    crew = Crew.query.get_or_404(crew_id)
    if request.method == 'POST':
        if crew and current_user.crew_id == crew.id:
            crew.name = request.form.get('name', crew.name)
            crew.photo = request.form.get('photo', crew.photo)
            crew.mp3_file = request.form.get('mp3_file', crew.mp3_file)
            crew.description = request.form.get('description', crew.description)
            db.session.commit()
            return redirect(url_for('index'))
        else:
            flash('Vous n\'avez pas les permissions pour modifier cet équipage.', 'error')
            return redirect(url_for('index'))
    return render_template('edit_crew.html', crew=crew)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def index():
    crews = Crew.query.all()
    return render_template('index.html', crews=crews)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
