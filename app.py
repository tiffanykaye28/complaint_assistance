from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask import session

app = Flask(__name__)
app.secret_key = 'secret_key_ani_para_sa_flash_messages' 

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///complaints.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=True) 
    full_name = db.Column(db.String(100), nullable=True)  # <--- IDUGANG NI
    email = db.Column(db.String(100), unique=True, nullable=True)      
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False) # <--- IDUGANG KINI
    status = db.Column(db.String(20), default='Pending')
    date_posted = db.Column(db.String(20), default=datetime.now().strftime("%m/%d/%y"))
with app.app_context():
    db.create_all() 
    
    if not User.query.filter_by(email="admin@gmail.com").first():
        admin = User(
            email="admin@gmail.com", 
            password="admin123", 
            role="staff"
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin account created!")

    # --- ROUTES ---

@app.route('/')
def index():
        return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('email_or_id')
        password = request.form.get('password')

        if username == "admin@gmail.com" and password == "admin123":
            session['user_role'] = 'staff'
            return redirect(url_for('admin_dashboard_route'))

        user = User.query.filter_by(student_id=username, password=password, role='student').first()
        if user:
            session['user_id'] = user.id 
            return redirect(url_for('student_home')) 

        flash("Invalid Credentials!")
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear() 
    flash("You have been logged out.")
    return redirect(url_for('login'))

@app.route('/student_home')
def student_home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_user = User.query.get(session['user_id'])
    
    user_complaints = Complaint.query.filter_by(student_name=current_user.student_id).all() 
    
    return render_template('student_home.html', user=current_user, complaints=user_complaints)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name') 
        s_id = request.form.get('student_id')
        pw = request.form.get('password')
        
        if User.query.filter_by(student_id=s_id).first():
            return "Student ID already registered!"

        new_student = User(student_id=s_id, full_name=full_name, password=pw, role='student')
        db.session.add(new_student)
        db.session.commit()
        return redirect(url_for('success')) 
        
    return render_template('register.html')

@app.route('/admin_dashboard')
def admin_dashboard_route():
    try:
        total = Complaint.query.count()
        pending = Complaint.query.filter_by(status='Pending').count()
        resolved = Complaint.query.filter_by(status='Resolved').count()
        
        stats = {
            'total': total,
            'pending': pending,
            'resolved': resolved,
            'this_month': 0  
        }

        all_complaints = Complaint.query.order_by(Complaint.id.desc()).all()
        
        return render_template('admin_dashboard.html', 
                               stats=stats, 
                               complaints=all_complaints)
    except Exception as e:
        return f"Error: {e}"

@app.route('/success')
def success():
        return render_template('success.html')




@app.route('/submit_complaint', methods=['GET', 'POST'])
def submit_complaint():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        category = request.form.get('category')
        desc = request.form.get('description') # <--- Idugang ni para makuha ang text
        
        new_complaint = Complaint(
            student_name=current_user.student_id, 
            category=category,
            description=desc, # <--- I-save kini sa DB
            status='Pending'
        )
        db.session.add(new_complaint)
        db.session.commit()
        flash("Complaint submitted successfully!") # Maayo ni para naay feedback
        return redirect(url_for('student_home'))
        
    return render_template('submit_complaint.html', user=current_user)


@app.route('/resolve_complaint/<int:id>')
def resolve_complaint(id):
    # Siguroha nga ang naka-login kay staff
    if session.get('user_role') != 'staff':
        flash("Unauthorized access!")
        return redirect(url_for('login'))
        
    complaint = Complaint.query.get_or_404(id)
    complaint.status = 'Resolved' # Usbon ang status sa DB
    db.session.commit()
    
    flash(f"Complaint #{id} marked as Resolved!")
    return redirect(url_for('admin_dashboard_route'))


if __name__ == '__main__':
        app.run(debug=True, port=8080)


