from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = 'secret_key_ani_para_sa_flash_messages'

# 1. DATABASE CONFIGURATION
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///complaints.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# 2. MODELS
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=True)
    full_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    # Dynamic date format para sa reports
    date_posted = db.Column(db.String(20), default=lambda: datetime.now().strftime("%m/%d/%y"))


# 3. AUTO-CREATE DB AND ADMIN
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
        print("Admin account created: admin@gmail.com / admin123")


# 4. ROUTES

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('email_or_id')
        password = request.form.get('password')

        print(f"DEBUG: Login attempt with: {username}")  # Makita ni sa terminal

        # 1. Admin Hardcoded Check
        if username == "admin@gmail.com" and password == "admin123":
            session['user_role'] = 'staff'
            return redirect(url_for('admin_dashboard_route'))

        # 2. Database Check (Pangitaon ang user base sa Email o ID)
        user = User.query.filter((User.student_id == username) | (User.email == username)).filter_by(
            password=password).first()

        if user:
            session['user_id'] = user.id
            session['user_role'] = user.role
            print(f"DEBUG: Login Success! Role: {user.role}")

            if user.role == 'staff':
                return redirect(url_for('admin_dashboard_route'))
            return redirect(url_for('student_home'))

        print("DEBUG: Login Failed - Invalid Credentials")
        flash("Sayo ang ID/Email o Password!")
        return redirect(url_for('login'))

    return render_template('login.html')
@app.route('/admin_dashboard')
def admin_dashboard_route():
    if session.get('user_role') != 'staff':
        return redirect(url_for('login'))

    try:
        current_month_prefix = datetime.now().strftime("%m/")

        cat_data = db.session.query(
            Complaint.category,
            func.count(Complaint.id)
        ).filter(
            Complaint.date_posted.like(f"{current_month_prefix}%")
        ).group_by(Complaint.category).all()

        cat_labels = [row[0] for row in cat_data]
        cat_values = [row[1] for row in cat_data]

        total = Complaint.query.count()
        pending = Complaint.query.filter_by(status='Pending').count()
        resolved = Complaint.query.filter_by(status='Resolved').count()
        this_month_count = Complaint.query.filter(Complaint.date_posted.like(f"{current_month_prefix}%")).count()

        stats = {'total': total, 'pending': pending, 'resolved': resolved, 'this_month': this_month_count}
        all_complaints = Complaint.query.order_by(Complaint.id.desc()).all()
        trend_values = [Complaint.query.filter(Complaint.date_posted.like(f"{str(i).zfill(2)}/%")).count() for i in range(1, 13)]

        return render_template('admin_dashboard.html',
                               stats=stats,
                               complaints=all_complaints,
                               cat_labels=cat_labels,
                               cat_values=cat_values,
                               trend_values=trend_values)
    except Exception as e:
        return f"Error: {e}"
@app.route('/student_home')
def student_home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user = User.query.get(session['user_id'])
    # Get only complaints from this student
    user_complaints = Complaint.query.filter_by(student_name=current_user.student_id).all()
    return render_template('student_home.html', user=current_user, complaints=user_complaints)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        s_id = request.form.get('student_id')
        pw = request.form.get('password')

        if User.query.filter_by(student_id=s_id).first():
            flash("Student ID already registered!")
            return redirect(url_for('register'))

        new_student = User(student_id=s_id, full_name=full_name, password=pw, role='student')
        db.session.add(new_student)
        db.session.commit()
        flash("Registration Successful! Please Login.")
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/submit_complaint', methods=['GET', 'POST'])
def submit_complaint():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user = User.query.get(session['user_id'])

    if request.method == 'POST':
        category = request.form.get('category')
        desc = request.form.get('description')

        new_complaint = Complaint(
            student_name=current_user.student_id,
            category=category,
            description=desc
        )
        db.session.add(new_complaint)
        db.session.commit()
        flash("Complaint submitted!")
        return redirect(url_for('student_home'))

    return render_template('student_complaint_form.html', user=current_user)


@app.route('/resolve_complaint/<int:id>')
def resolve_complaint(id):
    if session.get('user_role') != 'staff':
        return redirect(url_for('login'))

    complaint = Complaint.query.get_or_404(id)
    complaint.status = 'Resolved'
    db.session.commit()
    flash(f"Complaint #{id} resolved!")
    return redirect(url_for('admin_dashboard_route'))


@app.route('/admin/complaint/<int:id>')
def admin_complaints_review(id):  # KINI NGA NGALAN DAPAT MATCH SA url_for
    if session.get('user_role') != 'staff':
        return redirect(url_for('login'))
    # ... rest of the code

@app.route('/admin/complaints')
def admin_complaints():
    if session.get('user_role') != 'staff':
        return redirect(url_for('login'))

    search_query = request.args.get('search', '')
    category_filter = request.args.get('category', 'All Categories')
    status_filter = request.args.get('status', 'All Statuses')

    # Sugdan ang query sa tanang complaints
    query = Complaint.query

    # 1. Search Logic: Mangita sa Student ID o Category
    if search_query:
        query = query.filter(
            (Complaint.student_name.contains(search_query)) |
            (Complaint.category.contains(search_query))
        )

    # 2. Category Filter Logic
    if category_filter != 'All Categories':
        query = query.filter(Complaint.category == category_filter)

    # 3. Status Filter Logic
    if status_filter != 'All Statuses':
        query = query.filter(Complaint.status == status_filter)

    # I-sort gikan sa pinaka-bag-o (descending order)
    all_complaints = query.order_by(Complaint.id.desc()).all()

    return render_template('admin_complaints.html',
                           complaints=all_complaints,
                           search_query=search_query,
                           category_filter=category_filter,
                           status_filter=status_filter)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/complaints/view/<int:id>')
def admin_complaints_view(id):
    if session.get('user_role') != 'staff':
        return redirect(url_for('login'))

    complaint = Complaint.query.get_or_404(id)
    return render_template('admin_complaints_view.html', complaint=complaint)

@app.route('/admin/complaints/view/<int:id>/update_status', methods=['POST'])
def update_complaint_status(id):
    if session.get('user_role') != 'staff':
        return redirect(url_for('login'))

    complaint = Complaint.query.get_or_404(id)
    new_status = request.form.get('status')  # status sent from form
    if new_status:
        complaint.status = new_status
        db.session.commit()
        flash(f"Complaint #{id} status updated to {new_status}!")

    # Redirect back to the same complaint view page
    return redirect(url_for('admin_complaints_view', id=id))



if __name__ == '__main__':
    # Siguroha nga mo-andar sa port 8080
    app.run(debug=True, port=8080)