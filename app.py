from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import func
from sqlalchemy import or_ # Siguroha nga naa kini sa taas sa imong app.py

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///complaints.db'
db = SQLAlchemy(app)

# --- MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True)
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'Guidance', 'DeptHead', 'student'
    course = db.Column(db.String(100)) # <--- I-add kini nga column
    dept_access = db.Column(db.String(100)) # e.g., 'Student Life'
    
class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50)) # <--- Kini ang gi-erroran
    student_name = db.Column(db.String(100))
    category = db.Column(db.String(50))
    department = db.Column(db.String(100))
    description = db.Column(db.Text)
    admin_remarks = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Pending')
    date_posted = db.Column(db.String(20))
    image_file = db.Column(db.String(100), nullable=True)
    last_updated = db.Column(db.String(100), nullable=True)


class ComplaintResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaint.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date_sent = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships to easily get the sender's name
    sender = db.relationship('User', backref='responses')



# --- AUTOMATIC MAPPING LOGIC ---
def get_department(category):
    mapping = {
        'Teacher Issue': 'Faculty Affairs',
        'Academic': 'Faculty Affairs',
        'Scholarship': 'Student Life',
        'Facility Issue': 'Facilities & Maintenance',
        'Bullying': 'Student Affairs Office',
        'Lost & Found Items': 'Student Affairs Office',
        'Document Request': 'Registrar Office',
        'Financial/Clearance': 'Accounting Office'
    }
    return mapping.get(category, 'General Affairs')
    
# 3. AUTO-CREATE DB AND ADMIN
with app.app_context():
    db.create_all()
    admin_check = User.query.filter_by(email='admin@gmail.com').first()
    if not admin_check:
        new_admin = User(
            email='admin@gmail.com',
            student_id='ADMIN-001', 
            password='123',
            full_name='Super Admin',
            role='Guidance'
        )
        db.session.add(new_admin)
        db.session.commit()


# 4. ROUTES

@app.route('/')
def index():
    return render_template('index.html')

from sqlalchemy import or_ 


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form.get('student_id') 
        password = request.form.get('password')

        # Mao ni ang sakto nga query:
        user = User.query.filter(
            or_(User.email == user_input, User.student_id == user_input),
            User.password == password
        ).first()

        if user:
            session['user_id'] = user.id
            session['user_role'] = user.role
            
            if user.role in ['Guidance', 'DeptHead', 'staff']:
                return redirect(url_for('admin_dashboard_route'))
            else:
                return redirect(url_for('student_home'))
        
        flash("Invalid ID/Email or Password!")
    return render_template('login.html')

@app.route('/admin_dashboard')
def admin_dashboard_route():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    admin_user = User.query.get(session['user_id'])
    
    # 1. ROLE-BASED FILTERING
    if admin_user.role == 'Guidance':
        # Super Admin sees everything
        base_query = Complaint.query
    else:
        # DeptHeads only see complaints matching their dept_access
        base_query = Complaint.query.filter_by(department=admin_user.dept_access)

    # 2. CALCULATE STATS (Kini ang kulang nimo mao nag error)
    stats = {
        'total': base_query.count(),
        'pending': base_query.filter_by(status='Pending').count(),
        'resolved': base_query.filter_by(status='Resolved').count()
    }

    # 3. GET ALL COMPLAINTS
    all_complaints = base_query.order_by(Complaint.id.desc()).all()

    # 4. RENDER TEMPLATE (Siguroha nga naay stats=stats sa tumoy)
    return render_template(
        'admin_dashboard.html', 
        complaints=all_complaints, 
        user=admin_user, 
        stats=stats
    )

@app.route('/post_response/<int:complaint_id>', methods=['POST'])
def post_response(complaint_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    message = request.form.get('message')
    if message:
        new_res = ComplaintResponse(
            complaint_id=complaint_id,
            user_id=session['user_id'],
            message=message,
            date_sent=datetime.now()
        )
        db.session.add(new_res)
        db.session.commit()
        flash("Response sent!")
    
    # Redirect back to whichever view they came from
    if session.get('user_role') == 'student':
        return redirect(url_for('view_complaint', complaint_id=complaint_id))
    else:
        return redirect(url_for('admin_complaints_view', id=complaint_id))

@app.route('/admin/departments')
def admin_departments():
    if session.get('user_role') not in ['staff', 'Guidance', 'DeptHead']:
        return redirect(url_for('login'))
    return render_template('admin_departments.html')
    
@app.route('/admin/departments/academic')
def academic_departments():
    if session.get('user_role') not in ['staff', 'Guidance', 'DeptHead']:
        return redirect(url_for('login'))
    return render_template('academic_departments.html')

@app.route('/admin/departments/functional')
def functional_departments():
    if session.get('user_role') not in ['staff', 'Guidance', 'DeptHead']:
        return redirect(url_for('login'))
    return render_template('functional_departments.html')


@app.route('/admin/categories')
def admin_categories():
    # Usba ang check para maapil ang Guidance ug DeptHead
    allowed_roles = ['staff', 'Guidance', 'DeptHead']
    if session.get('user_role') not in allowed_roles:
        return redirect(url_for('login'))

    # Get all unique categories from complaints
    categories = db.session.query(Complaint.category).distinct().all()

    # Convert list of tuples → list of strings
    categories = [c[0] for c in categories if c[0] is not None]

    return render_template('admin_categories.html', categories=categories)

@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    # 1. Check kon ang user usa ba sa mga admin roles
    allowed_roles = ['staff', 'Guidance', 'DeptHead']
    if session.get('user_role') not in allowed_roles:
        return redirect(url_for('login'))

    # 2. Kuhaon ang current user gikan sa session user_id
    admin_user = User.query.get(session['user_id'])

    if request.method == 'POST':
        new_email = request.form.get('email')
        new_password = request.form.get('password')
        new_name = request.form.get('full_name')

        if new_email:
            admin_user.email = new_email
        if new_password:
            admin_user.password = new_password
        if new_name:
            admin_user.full_name = new_name

        db.session.commit()
        flash("Settings updated successfully!")
        return redirect(url_for('admin_settings'))

    return render_template('admin_settings.html', user=admin_user)

def seed_data():
    admins = [
        # Gidugangan nato og 'sid' para naay i-input sa login form
        {'email': 'admin@gmail.com', 'pass': '123', 'role': 'Guidance', 'dept': 'All', 'sid': 'ADMIN-001'},
        {'email': 'faculty@gmail.com', 'pass': '123', 'role': 'DeptHead', 'dept': 'Faculty Affairs', 'sid': 'ADM-002'},
        {'email': 'sao@gmail.com', 'pass': '123', 'role': 'DeptHead', 'dept': 'Student Affairs Office', 'sid': 'ADM-003'},
        {'email': 'studentlife@gmail.com', 'pass': '123', 'role': 'DeptHead', 'dept': 'Student Life', 'sid': 'ADM-004'},
        {'email': 'facilities@gmail.com', 'pass': '123', 'role': 'DeptHead', 'dept': 'Facilities & Maintenance', 'sid': 'ADM-005'},
        {'email': 'finance@gmail.com', 'pass': '123', 'role': 'DeptHead', 'dept': 'Finance Office', 'sid': 'ADM-006'},
        {'email': 'registrar@gmail.com', 'pass': '123', 'role': 'DeptHead', 'dept': 'Registrar Office', 'sid': 'ADM-007'},
        {'email': 'accounting@gmail.com', 'pass': '123', 'role': 'DeptHead', 'dept': 'Accounting Office', 'sid': 'ADM-008'}
    ]
    for a in admins:
        if not User.query.filter_by(email=a['email']).first():
            new_admin = User(
                email=a['email'],
                student_id=a['sid'], # Siguroha nga 'sid' ang gamiton
                password=a['pass'],
                role=a['role'],
                dept_access=a['dept'],
                full_name=f"{a['dept']} Admin",
                course="N/A"
            )
            db.session.add(new_admin)
    db.session.commit()


@app.route('/student/home')
def student_home():
    # 1. Siguroha nga naka-login
    if 'user_id' not in session or session.get('user_role') != 'student':
        return redirect(url_for('login'))
    
    # 2. Kuhaon ang data sa student gikan sa database gamit ang session ID
    current_user = User.query.get(session['user_id'])
    
    # 3. I-pass ang 'user' object ngadto sa template
    # Kini ang 'user' nga gipangita sa imong HTML (line 61)
    return render_template('student_home.html', user=current_user)

# Siguroha nga wala nay laing "def student_account" sa taas o ubos niini
@app.route('/student/account', methods=['GET', 'POST'])
def student_account():
    if 'user_id' not in session or session.get('user_role') != 'student':
        return redirect(url_for('login'))
    
    user_data = User.query.get(session['user_id'])

    if request.method == 'POST':
        new_email = request.form.get('email')
        new_pass = request.form.get('password')

        if new_email:
            user_data.email = new_email
        
        if new_pass:
            user_data.password = new_pass
            
        db.session.commit()
        flash("Settings updated successfully!")
        return redirect(url_for('student_account'))

    return render_template('student_account.html', user=user_data)

@app.route('/register', methods=['GET', 'POST'])
def register():
    scc_courses = [
        {'id': 1, 'name': 'BS in Nursing'},
        {'id': 2, 'name': 'BS in Information Technology'},
        {'id': 3, 'name': 'BS in Business Administration'},
        {'id': 4, 'name': 'BS in Management Accounting'},
        {'id': 5, 'name': 'BS in Tourism Management'},
        {'id': 6, 'name': 'BS in Hospitality Management'},
        {'id': 7, 'name': 'BS in Criminology'},
        {'id': 8, 'name': 'BEED - General Education'},
        {'id': 9, 'name': 'BSED - English and Mathematics'},
        {'id': 10, 'name': 'Associate in Computer Technology'}
    ]

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        s_id = request.form.get('student_id')
        password = request.form.get('password')
        course_id = request.form.get('course_id')

        # 1. Check kon ang Student ID nagamit na
        if User.query.filter_by(student_id=s_id).first():
            flash("Student ID already registered!")
            return redirect(url_for('register'))

        # 2. Check kon ang Email nagamit na (KINI ANG SOLUSYON SA ERROR)
        if User.query.filter_by(email=email).first():
            flash("Email address already registered!")
            return redirect(url_for('register'))

        # Pangitaon ang name sa course base sa ID
        selected_course = "Not Specified"
        for c in scc_courses:
            if str(c['id']) == course_id:
                selected_course = c['name']
                break

        # 3. Create new user kon pasado sa tanang checks
        new_student = User(
            student_id=s_id,
            full_name=full_name,
            email=email,
            password=password,
            course=selected_course,
            role='student'
        )
        
        try:
            db.session.add(new_student)
            db.session.commit()
            flash("Registration Successful!")
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash("An error occurred during registration. Please try again.")
            return redirect(url_for('register'))

    return render_template('register.html', courses=scc_courses)

@app.route('/submit_complaint', methods=['GET', 'POST'])
def submit_complaint():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user = User.query.get(session['user_id'])

    if request.method == 'POST':
        category = request.form.get('category')
        description = request.form.get('description')
        
        file = request.files.get('complaint_photo')
        filename = None
        
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            upload_path = os.path.join('static', 'uploads')
            
            if not os.path.exists(upload_path):
                os.makedirs(upload_path)

            file.save(os.path.join(upload_path, filename))

        # 3. Department Mapping (Sakto na ang Syntax diri)
        dept_mapping = {
            'Teacher Issue': 'Faculty Affairs',
            'Academic': 'Faculty Affairs',
            'Scholarship': 'Student Life',
            'Facility Issue': 'Facilities & Maintenance',
            'Bullying': 'Student Affairs Office',
            'Lost & Found Items': 'Student Affairs Office',
            'Document Request': 'Registrar Office',
            'Financial/Clearance': 'Accounting Office',  # Naa nay comma diri
            'Tuition & Fees Discrepancy': 'Accounting Office'
        }
        
        # Kini ang 'mag-base' ditso sa unsay gi-select sa student
        # Siguroha lang nga ang spelling sa HTML 'value' parehas gyud sa dictionary keys
        try:
            assigned_dept = dept_mapping[category]
        except KeyError:
            # Kung naay karaan nga category sa browser, i-default lang una aron dili mo-crash
            assigned_dept = 'Accounting Office'

        # 4. I-save sa Database
        new_complaint = Complaint(
            student_id=current_user.student_id,
            student_name=current_user.full_name,
            category=category,
            description=description,
            department=assigned_dept, # Automatic assignment base sa category
            image_file=filename,
            status='Pending',
            date_posted=datetime.now().strftime("%B %d, %Y")
        )
        
        db.session.add(new_complaint)
        db.session.commit()

        flash(f"Complaint submitted and assigned to {assigned_dept}!")
        return redirect(url_for('student_home'))

    return render_template('student_complaint_form.html', user=current_user)


@app.route('/student_all_complaints')
def student_all_complaints():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user = User.query.get(session['user_id'])
    
    # Siguroha nga 'student_id' ang i-filter para unique gyud sa student
    complaints = Complaint.query.filter_by(student_id=current_user.student_id).order_by(Complaint.id.desc()).all()

    return render_template('student_all_complaints.html', user=current_user, complaints=complaints)



@app.route('/complaint/<int:complaint_id>')
def view_complaint(complaint_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    complaint = Complaint.query.get_or_404(complaint_id)
    
    # Kinahanglan i-fetch ang student data base sa student_id nga naa sa complaint
    student = User.query.filter_by(student_id=complaint.student_id).first()

    # I-pass ang 'complaint' UG 'student' sa HTML
    return render_template('view_complaint.html', complaint=complaint, student=student)

@app.route('/resolve_complaint/<int:id>')
def resolve_complaint(id):
    if session.get('user_role') != 'staff':
        return redirect(url_for('login'))

    complaint = Complaint.query.get_or_404(id)
    complaint.status = 'Resolved'
    db.session.commit()
    flash(f"Complaint #{id} resolved!")
    return redirect(url_for('admin_dashboard_route'))

@app.route('/admin_complaints')
def admin_complaints():
    # I-allow ang tanang admin roles para dili ma-redirect
    allowed_roles = ['staff', 'Guidance', 'DeptHead']
    
    if 'user_id' not in session or session.get('user_role') not in allowed_roles:
        return redirect(url_for('login'))

    # Kuhaon ang data gikan sa URL filters
    dept = request.args.get('department', '').strip()
    status = request.args.get('status', '').strip()

    # Base Query
    query = Complaint.query

    # I-apply ang filters
    if dept:
        query = query.filter(Complaint.department.ilike(f"%{dept}%"))
    if status:
        query = query.filter(Complaint.status.ilike(f"%{status}%"))

    complaints = query.order_by(Complaint.id.desc()).all()
    
    return render_template('admin_complaints.html', complaints=complaints)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Kinahanglan naay <int:id> sa URL path
@app.route('/admin/view_complaints/<int:id>') 
def admin_complaints_view(id): # <--- Siguroha nga naay 'id' diri
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user = User.query.get(session['user_id'])
    
    # Karon, ang 'id' kay usa na ka integer gikan sa URL, dili na built-in function
    single_complaint = Complaint.query.get_or_404(id)
    
    # Kinahanglan pud nato i-fetch ang student para sa profile sa HTML
    student = User.query.filter_by(student_id=single_complaint.student_id).first()

    return render_template('admin_view_complaints.html', 
                           user=current_user, 
                           complaint=single_complaint,
                           student=student)


@app.route('/admin/complaints/view/<int:id>/update_status', methods=['POST'])
def update_complaint_status(id):
    allowed_roles = ['Guidance', 'DeptHead', 'staff']
    if session.get('user_role') not in allowed_roles:
        return redirect(url_for('login'))

    complaint = Complaint.query.get_or_404(id)
    new_status = request.form.get('new_status') 
    admin_response = request.form.get('admin_response') # Kuhaon ang text gikan sa textarea

    if new_status:
        complaint.status = new_status
        # I-save ang response/remarks kung naay gi-input ang admin
        if admin_response:
            complaint.admin_remarks = admin_response 
        
        # I-update ang timestamp para sa Log Activity
        complaint.last_updated = datetime.now().strftime("%B %d, %Y")
        
        db.session.commit()
        flash(f"Complaint #{id} updated successfully!")

    return redirect(url_for('admin_complaints_view', id=id))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
    # Usba gikan sa 8080 ngadto sa 5000
    app.run(debug=True, port=5000)