"""
AI-Powered College Event Management System
==========================================
Backend: Python Flask
Database: SQLite (MySQL-compatible schema)
AI: Rule-based recommendation, prediction & chatbot
Modules: Admin | Organizer | Student
"""

import sqlite3, hashlib, secrets, json, os, base64, io, math
from datetime import datetime, timedelta
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify, g)

# ── AI Engine ──────────────────────────────────────────────
from ai.engine import (recommend_events, predict_attendance,
                       check_conflicts, chatbot_response,
                       generate_qr_token, generate_qr_svg,
                       check_venue_availability, generate_event_template)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
DATABASE = os.path.join(os.path.dirname(__file__), 'cems.db')


# ════════════════════════════════════════════════════════════
#  DATABASE
# ════════════════════════════════════════════════════════════
def get_db():
    db = getattr(g, '_db', None)
    if db is None:
        db = g._db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(e):
    db = getattr(g, '_db', None)
    if db: db.close()

def q(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def ex(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid

def hp(pw): return hashlib.sha256(pw.encode()).hexdigest()


def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                department TEXT,
                year TEXT,
                reg_no TEXT,
                interests TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS venues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                location TEXT,
                facilities TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                end_time TEXT,
                venue_id INTEGER,
                organizer_id INTEGER NOT NULL,
                max_participants INTEGER DEFAULT 100,
                status TEXT DEFAULT 'pending',
                tags TEXT DEFAULT '[]',
                registration_fee REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(venue_id) REFERENCES venues(id),
                FOREIGN KEY(organizer_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                attended INTEGER DEFAULT 0,
                feedback TEXT,
                rating INTEGER,
                UNIQUE(user_id, event_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(event_id) REFERENCES events(id)
            );

            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS qr_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, event_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(event_id) REFERENCES events(id)
            );

            CREATE TABLE IF NOT EXISTS event_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, event_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(event_id) REFERENCES events(id)
            );
        ''')
        db.commit()
        # Migrate existing DB - add new columns if missing
        try:
            db.execute("ALTER TABLE events ADD COLUMN registration_fee REAL DEFAULT 0")
            db.commit()
        except: pass
        _seed_data(db)


def _seed_data(db):
    if q("SELECT id FROM users WHERE email='admin@college.edu'", one=True):
        return  # already seeded

    # Users
    users = [
        ('Admin User',    'admin@college.edu',     hp('admin123'),     'admin',     'Administration', None, None, '[]'),
        ('Dr. Raj Kumar', 'organizer@college.edu', hp('org123'),       'organizer', 'Computer Science', None, None, '["Tech","Workshop"]'),
        ('Prof. Meena',   'meena@college.edu',     hp('org123'),       'organizer', 'Cultural Arts', None, None, '["Cultural","Music"]'),
        ('Rohan Mehta',   'rohan@student.edu',     hp('student123'),   'student',   'Computer Science', '3rd Year', 'CS2023048', '["Tech","Workshop","AI"]'),
        ('Priya Singh',   'priya@student.edu',     hp('student123'),   'student',   'Information Tech', '2nd Year', 'IT2024031', '["Cultural","Dance","Music"]'),
        ('Aditya Kumar',  'aditya@student.edu',    hp('student123'),   'student',   'Mechanical Engg', '3rd Year', 'ME2023015', '["Sports","Tech"]'),
    ]
    for u in users:
        db.execute("INSERT INTO users (name,email,password,role,department,year,reg_no,interests) VALUES (?,?,?,?,?,?,?,?)", u)

    # Venues
    venues = [
        ('Main Auditorium', 500, 'Block A, Ground Floor', 'Projector, Sound System, AC'),
        ('Seminar Hall A',  150, 'Block B, 2nd Floor',    'Projector, Whiteboard, AC'),
        ('Sports Ground',   800, 'Campus Ground',         'Open Field, Floodlights'),
        ('Lab 301',          50, 'Block C, 3rd Floor',    'Computers, Projector, AC'),
        ('Gallery Hall',    200, 'Art Block, 1st Floor',  'Display Walls, AC'),
        ('Open Amphitheatre',300,'Campus Center',         'Stage, Sound System'),
    ]
    for v in venues:
        db.execute("INSERT INTO venues (name,capacity,location,facilities) VALUES (?,?,?,?)", v)

    # Events
    events = [
        ('National Hackathon 2025',     'Tech',     'A 24-hour hackathon. Build innovative solutions and win ₹1,50,000!',        '2025-03-15','09:00','21:00', 1, 2, 200, 'approved', '["hackathon","coding","AI"]'),
        ('Annual Cultural Fest',        'Cultural', 'Celebrate art, music, dance and drama in our flagship cultural event.',      '2025-03-22','10:00','20:00', 1, 3, 500, 'approved', '["music","dance","art"]'),
        ('React.js Workshop',           'Workshop', 'Hands-on workshop on React.js: hooks, context API, and deployment.',         '2025-04-10','14:00','17:00', 4, 2, 50,  'approved', '["react","web","frontend"]'),
        ('AI & ML Symposium',           'Tech',     'Industry experts on latest AI/ML trends. Networking session included.',      '2025-05-05','10:00','16:00', 2, 2, 150, 'approved', '["AI","ML","data science"]'),
        ('Photography Exhibition',      'Cultural', 'Student photography showcase: nature, urban life, and human emotions.',      '2025-04-18','11:00','18:00', 5, 3, 300, 'approved', '["photography","art","exhibition"]'),
        ('Inter-College Cricket',       'Sports',   'Annual inter-college cricket championship. 16 teams compete!',               '2025-04-01','08:00','18:00', 3, 2, 100, 'approved', '["cricket","sports","tournament"]'),
        ('Cybersecurity Bootcamp',      'Workshop', 'Hands-on ethical hacking, penetration testing and security tools.',         '2025-05-15','09:00','17:00', 4, 2, 40,  'pending',  '["cybersecurity","hacking","linux"]'),
        ('Classical Music Night',       'Cultural', 'An evening of Hindustani and Carnatic classical music performances.',        '2025-05-20','18:00','21:00', 6, 3, 250, 'pending',  '["music","classical","performance"]'),
    ]
    for e in events:
        db.execute("INSERT INTO events (title,category,description,date,time,end_time,venue_id,organizer_id,max_participants,status,tags) VALUES (?,?,?,?,?,?,?,?,?,?,?)", e)

    # Registrations (Rohan → Tech events, Priya → Cultural)
    regs = [(4,1,1),(4,3,1),(4,4,0),(5,2,1),(5,5,0),(6,6,1),(6,1,0)]
    for r in regs:
        db.execute("INSERT OR IGNORE INTO registrations (user_id,event_id,attended) VALUES (?,?,?)", r)

    # Activity log
    logs = [
        (1,'USER_LOGIN','Admin logged in'),
        (4,'EVENT_REGISTER','Registered for Hackathon'),
        (5,'EVENT_REGISTER','Registered for Cultural Fest'),
        (2,'EVENT_CREATE','Created React.js Workshop'),
    ]
    for l in logs:
        db.execute("INSERT INTO activity_log (user_id,action,details) VALUES (?,?,?)", l)

    db.commit()


# ════════════════════════════════════════════════════════════
#  AUTH DECORATORS
# ════════════════════════════════════════════════════════════
def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if 'user_id' not in session:
            flash('Please log in.', 'error')
            return redirect(url_for('login'))
        return f(*a, **kw)
    return dec

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def dec(*a, **kw):
            if session.get('role') not in roles:
                flash('Access denied.', 'error')
                return redirect(url_for('login'))
            return f(*a, **kw)
        return dec
    return decorator

def log_action(user_id, action, details=''):
    try:
        ex("INSERT INTO activity_log (user_id,action,details) VALUES (?,?,?)",
           (user_id, action, details))
    except: pass


# ════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ════════════════════════════════════════════════════════════
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    role = session.get('role')
    return redirect(url_for({'admin':'admin_dashboard','organizer':'org_dashboard','student':'student_events'}.get(role,'login')))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        pw    = request.form.get('password','').strip()
        user  = q("SELECT * FROM users WHERE email=? AND password=?", (email, hp(pw)), one=True)
        if user:
            session.update({'user_id':user['id'],'name':user['name'],'role':user['role'],'email':user['email']})
            log_action(user['id'], 'USER_LOGIN', f'{user["role"]} login')
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(url_for(index.__name__))
        flash('Invalid credentials.', 'error')
    return render_template('auth/login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        data = {k: request.form.get(k,'').strip() for k in ['name','email','password','department','year','reg_no']}
        role      = request.form.get('role', 'student').strip()
        interests = request.form.getlist('interests')
        if role not in ('student', 'organizer'):
            role = 'student'
        if not all([data['name'], data['email'], data['password']]):
            flash('Name, email and password required.','error')
            return render_template('auth/register.html')
        if len(data['password']) < 6:
            flash('Password must be at least 6 characters.','error')
            return render_template('auth/register.html')
        if q("SELECT id FROM users WHERE email=?", (data['email'],), one=True):
            flash('Email already registered.','error')
            return render_template('auth/register.html')
        uid = ex("INSERT INTO users (name,email,password,role,department,year,reg_no,interests) VALUES (?,?,?,?,?,?,?,?)",
           (data['name'], data['email'], hp(data['password']), role,
            data['department'], data['year'] if role=='student' else None,
            data['reg_no'] if role=='student' else None, json.dumps(interests)))
        log_action(uid, 'USER_REGISTER', f'New {role} registered: {data["name"]}')
        if role == 'organizer':
            flash('Organizer account created! You can now log in and start creating events.', 'success')
        else:
            flash('Student account created! Please log in.', 'success')
        return redirect(url_for('login'))
    default_role = request.args.get('role', 'student')
    return render_template('auth/register.html', default_role=default_role)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.','success')
    return redirect(url_for('login'))


# ════════════════════════════════════════════════════════════
#  ADMIN ROUTES
# ════════════════════════════════════════════════════════════
@app.route('/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    stats = {
        'total_users':   q("SELECT COUNT(*) as c FROM users WHERE role='student'",one=True)['c'],
        'total_events':  q("SELECT COUNT(*) as c FROM events",one=True)['c'],
        'pending':       q("SELECT COUNT(*) as c FROM events WHERE status='pending'",one=True)['c'],
        'registrations': q("SELECT COUNT(*) as c FROM registrations",one=True)['c'],
        'organizers':    q("SELECT COUNT(*) as c FROM users WHERE role='organizer'",one=True)['c'],
        'approved':      q("SELECT COUNT(*) as c FROM events WHERE status='approved'",one=True)['c'],
    }
    recent_events = q("""SELECT e.*,u.name as org_name,v.name as venue_name
        FROM events e JOIN users u ON e.organizer_id=u.id
        LEFT JOIN venues v ON e.venue_id=v.id
        ORDER BY e.created_at DESC LIMIT 6""")
    activity = q("SELECT a.*,u.name as uname FROM activity_log a LEFT JOIN users u ON a.user_id=u.id ORDER BY a.timestamp DESC LIMIT 10")
    cat_stats = q("SELECT category, COUNT(*) as cnt FROM events GROUP BY category")
    return render_template('admin/dashboard.html', stats=stats,
                           recent_events=recent_events, activity=activity, cat_stats=cat_stats)

@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    role_filter = request.args.get('role','')
    if role_filter:
        users = q("SELECT * FROM users WHERE role=? ORDER BY created_at DESC", (role_filter,))
    else:
        users = q("SELECT * FROM users ORDER BY role, created_at DESC")
    return render_template('admin/users.html', users=users, role_filter=role_filter)

@app.route('/admin/users/delete/<int:uid>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_user(uid):
    ex("DELETE FROM users WHERE id=?", (uid,))
    flash('User deleted.','success')
    return redirect(url_for('admin_users'))

@app.route('/admin/events')
@login_required
@role_required('admin')
def admin_events():
    events = q("""SELECT e.*,u.name as org_name,v.name as venue_name,COUNT(r.id) as reg_count
        FROM events e JOIN users u ON e.organizer_id=u.id
        LEFT JOIN venues v ON e.venue_id=v.id
        LEFT JOIN registrations r ON e.id=r.event_id
        GROUP BY e.id ORDER BY e.date DESC""")
    return render_template('admin/events.html', events=events)

@app.route('/admin/events/approve/<int:eid>', methods=['POST'])
@login_required
@role_required('admin')
def approve_event(eid):
    ev = q("SELECT * FROM events WHERE id=?", (eid,), one=True)
    ex("UPDATE events SET status='approved' WHERE id=?", (eid,))
    # Notify organizer
    ex("INSERT INTO notifications (user_id,message) VALUES (?,?)",
       (ev['organizer_id'], f'Your event "{ev["title"]}" has been approved!'))
    log_action(session['user_id'],'EVENT_APPROVE', f'Approved event {eid}')
    flash('Event approved!','success')
    return redirect(url_for('admin_events'))

@app.route('/admin/events/reject/<int:eid>', methods=['POST'])
@login_required
@role_required('admin')
def reject_event(eid):
    ev = q("SELECT * FROM events WHERE id=?", (eid,), one=True)
    ex("UPDATE events SET status='rejected' WHERE id=?", (eid,))
    ex("INSERT INTO notifications (user_id,message) VALUES (?,?)",
       (ev['organizer_id'], f'Your event "{ev["title"]}" was not approved.'))
    flash('Event rejected.','error')
    return redirect(url_for('admin_events'))

@app.route('/admin/reports')
@login_required
@role_required('admin')
def admin_reports():
    # Registration trend (last 30 days simulated)
    top_events = q("""SELECT e.title, COUNT(r.id) as reg_count, e.category
        FROM events e JOIN registrations r ON e.id=r.event_id
        GROUP BY e.id ORDER BY reg_count DESC LIMIT 5""")
    dept_stats = q("""SELECT u.department, COUNT(r.id) as reg_count
        FROM registrations r JOIN users u ON r.user_id=u.id
        GROUP BY u.department ORDER BY reg_count DESC""")
    attendance_rate = q("""SELECT e.title,
        COUNT(r.id) as total, SUM(r.attended) as attended
        FROM events e JOIN registrations r ON e.id=r.event_id
        WHERE e.status='approved' GROUP BY e.id""")
    return render_template('admin/reports.html',
        top_events=top_events, dept_stats=dept_stats, attendance_rate=attendance_rate)

@app.route('/admin/venues')
@login_required
@role_required('admin')
def admin_venues():
    venues = q("SELECT * FROM venues")
    return render_template('admin/venues.html', venues=venues)


# ════════════════════════════════════════════════════════════
#  ORGANIZER ROUTES
# ════════════════════════════════════════════════════════════
@app.route('/organizer')
@login_required
@role_required('organizer')
def org_dashboard():
    uid = session['user_id']
    my_events = q("""SELECT e.*,v.name as venue_name,COUNT(r.id) as reg_count
        FROM events e LEFT JOIN venues v ON e.venue_id=v.id
        LEFT JOIN registrations r ON e.id=r.event_id
        WHERE e.organizer_id=? GROUP BY e.id ORDER BY e.date DESC""", (uid,))
    stats = {
        'total': len(my_events),
        'approved': sum(1 for e in my_events if e['status']=='approved'),
        'pending':  sum(1 for e in my_events if e['status']=='pending'),
        'total_reg': sum(e['reg_count'] for e in my_events),
    }
    notifs = q("SELECT * FROM notifications WHERE user_id=? AND is_read=0 ORDER BY created_at DESC", (uid,))
    return render_template('organizer/dashboard.html', my_events=my_events, stats=stats, notifs=notifs)

@app.route('/organizer/events/create', methods=['GET','POST'])
@login_required
@role_required('organizer')
def org_create_event():
    venues = q("SELECT * FROM venues ORDER BY name")
    if request.method == 'POST':
        data = {k: request.form.get(k,'').strip() for k in
                ['title','category','description','date','time','end_time','venue_id','max_participants','tags']}
        fee = float(request.form.get('registration_fee', 0) or 0)
        # AI: conflict check
        conflicts = check_conflicts(data['venue_id'], data['date'], data['time'], data['end_time'])
        if conflicts:
            flash(f'⚠️ AI Conflict Detected: {conflicts}', 'error')
            return render_template('organizer/event_form.html', venues=venues, event=None, data=data)
        tags = json.dumps([t.strip() for t in data['tags'].split(',') if t.strip()])
        eid = ex("""INSERT INTO events (title,category,description,date,time,end_time,venue_id,
                    organizer_id,max_participants,status,tags,registration_fee) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (data['title'],data['category'],data['description'],data['date'],data['time'],
                  data['end_time'],data['venue_id'] or None,session['user_id'],
                  int(data['max_participants'] or 100),'pending',tags,fee))
        log_action(session['user_id'],'EVENT_CREATE',f'Created event: {data["title"]}')
        flash('Event submitted for admin approval!','success')
        return redirect(url_for('org_dashboard'))
    return render_template('organizer/event_form.html', venues=venues, event=None, data={})

@app.route('/organizer/events/edit/<int:eid>', methods=['GET','POST'])
@login_required
@role_required('organizer')
def org_edit_event(eid):
    event = q("SELECT * FROM events WHERE id=? AND organizer_id=?", (eid, session['user_id']), one=True)
    if not event:
        flash('Event not found.','error')
        return redirect(url_for('org_dashboard'))
    venues = q("SELECT * FROM venues ORDER BY name")
    if request.method == 'POST':
        data = {k: request.form.get(k,'').strip() for k in
                ['title','category','description','date','time','end_time','venue_id','max_participants','tags']}
        fee = float(request.form.get('registration_fee', 0) or 0)
        tags = json.dumps([t.strip() for t in data['tags'].split(',') if t.strip()])
        ex("""UPDATE events SET title=?,category=?,description=?,date=?,time=?,end_time=?,
              venue_id=?,max_participants=?,tags=?,registration_fee=?,status='pending' WHERE id=?""",
           (data['title'],data['category'],data['description'],data['date'],data['time'],
            data['end_time'],data['venue_id'] or None,int(data['max_participants'] or 100),tags,fee,eid))
        flash('Event updated and re-submitted for approval.','success')
        return redirect(url_for('org_dashboard'))
    return render_template('organizer/event_form.html', venues=venues, event=event, data=dict(event))

@app.route('/organizer/events/delete/<int:eid>', methods=['POST'])
@login_required
@role_required('organizer')
def org_delete_event(eid):
    ex("DELETE FROM registrations WHERE event_id=?", (eid,))
    ex("DELETE FROM events WHERE id=? AND organizer_id=?", (eid, session['user_id']))
    flash('Event deleted.','success')
    return redirect(url_for('org_dashboard'))

@app.route('/organizer/events/<int:eid>/registrations')
@login_required
@role_required('organizer')
def org_registrations(eid):
    event = q("SELECT * FROM events WHERE id=? AND organizer_id=?", (eid, session['user_id']), one=True)
    if not event:
        flash('Not found.','error')
        return redirect(url_for('org_dashboard'))
    regs = q("""SELECT r.*,u.name,u.email,u.department,u.reg_no
        FROM registrations r JOIN users u ON r.user_id=u.id
        WHERE r.event_id=? ORDER BY r.registered_at""", (eid,))
    # AI attendance prediction
    prediction = predict_attendance(eid, len(regs), event['max_participants'],
                                    event['category'], event['date'])
    return render_template('organizer/registrations.html', event=event,
                           registrations=regs, prediction=prediction)

@app.route('/organizer/events/<int:eid>/attendance', methods=['POST'])
@login_required
@role_required('organizer')
def mark_attendance(eid):
    attended_ids = request.form.getlist('attended')
    ex("UPDATE registrations SET attended=0 WHERE event_id=?", (eid,))
    for uid in attended_ids:
        ex("UPDATE registrations SET attended=1 WHERE event_id=? AND user_id=?", (eid, uid))
    flash(f'Attendance marked for {len(attended_ids)} students.','success')
    return redirect(url_for('org_registrations', eid=eid))


# ════════════════════════════════════════════════════════════
#  STUDENT ROUTES
# ════════════════════════════════════════════════════════════
@app.route('/student/events')
@login_required
@role_required('student')
def student_events():
    uid = session['user_id']
    cat    = request.args.get('category','')
    search = request.args.get('search','')
    sql = """SELECT e.*,u.name as org_name,v.name as venue_name,
             COUNT(r2.id) as reg_count,
             SUM(CASE WHEN r2.user_id=? THEN 1 ELSE 0 END) as is_registered
             FROM events e JOIN users u ON e.organizer_id=u.id
             LEFT JOIN venues v ON e.venue_id=v.id
             LEFT JOIN registrations r2 ON e.id=r2.event_id
             WHERE e.status='approved'"""
    args = [uid]
    if cat:   sql += " AND e.category=?"; args.append(cat)
    if search:sql += " AND e.title LIKE ?"; args.append(f'%{search}%')
    sql += " GROUP BY e.id ORDER BY e.date ASC"
    events = q(sql, args)

    # AI recommendations
    user = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
    interests = json.loads(user['interests'] or '[]')
    my_event_ids = [r['event_id'] for r in q("SELECT event_id FROM registrations WHERE user_id=?", (uid,))]
    all_events = q("SELECT * FROM events WHERE status='approved'")
    recommendations = recommend_events(interests, my_event_ids, all_events)

    categories = ['Tech','Cultural','Sports','Workshop','Music','Art']
    return render_template('student/events.html', events=events,
                           categories=categories, active_cat=cat, search=search,
                           recommendations=recommendations)

@app.route('/student/events/register/<int:eid>', methods=['POST'])
@login_required
@role_required('student')
def student_register(eid):
    uid  = session['user_id']
    ev   = q("SELECT * FROM events WHERE id=?", (eid,), one=True)
    cnt  = q("SELECT COUNT(*) as c FROM registrations WHERE event_id=?", (eid,), one=True)['c']
    if cnt >= ev['max_participants']:
        flash('Sorry, event is full!','error')
        return redirect(url_for('student_events'))
    try:
        ex("INSERT INTO registrations (user_id,event_id) VALUES (?,?)", (uid, eid))
        ex("INSERT INTO notifications (user_id,message) VALUES (?,?)",
           (uid, f'Successfully registered for "{ev["title"]}"!'))
        log_action(uid,'EVENT_REGISTER',f'Registered for event {eid}')
        flash(f'Registered for "{ev["title"]}"!','success')
    except:
        flash('Already registered.','error')
    return redirect(url_for('student_events'))

@app.route('/student/events/cancel/<int:eid>', methods=['POST'])
@login_required
@role_required('student')
def student_cancel(eid):
    ex("DELETE FROM registrations WHERE user_id=? AND event_id=?", (session['user_id'], eid))
    flash('Registration cancelled.','success')
    return redirect(url_for('my_registrations'))

@app.route('/student/my-events')
@login_required
@role_required('student')
def my_registrations():
    uid  = session['user_id']
    regs = q("""SELECT r.*,e.title,e.category,e.date,e.time,e.description,
                e.registration_fee,v.name as venue_name
                FROM registrations r JOIN events e ON r.event_id=e.id
                LEFT JOIN venues v ON e.venue_id=v.id
                WHERE r.user_id=? ORDER BY e.date ASC""", (uid,))
    # Fetch existing feedbacks
    fbs = q("SELECT * FROM event_feedback WHERE user_id=?", (uid,))
    feedbacks_map = {f['event_id']: dict(f) for f in fbs}
    return render_template('student/my_events.html', registrations=regs, feedbacks_map=feedbacks_map)

@app.route('/student/my-events/feedback/<int:eid>', methods=['POST'])
@login_required
@role_required('student')
def submit_feedback(eid):
    fb     = request.form.get('feedback','').strip()
    rating = request.form.get('rating','5')
    ex("UPDATE registrations SET feedback=?,rating=? WHERE user_id=? AND event_id=?",
       (fb, rating, session['user_id'], eid))
    flash('Feedback submitted, thank you!','success')
    return redirect(url_for('my_registrations'))

@app.route('/student/profile')
@login_required
@role_required('student')
def student_profile():
    uid  = session['user_id']
    user = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
    stats = {
        'registered': q("SELECT COUNT(*) as c FROM registrations WHERE user_id=?", (uid,), one=True)['c'],
        'attended':   q("SELECT COUNT(*) as c FROM registrations WHERE user_id=? AND attended=1", (uid,), one=True)['c'],
    }
    history = q("""SELECT r.*,e.title,e.category,e.date
        FROM registrations r JOIN events e ON r.event_id=e.id
        WHERE r.user_id=? ORDER BY e.date DESC""", (uid,))
    return render_template('student/profile.html', user=user, stats=stats, history=history)


# ════════════════════════════════════════════════════════════
#  SHARED ROUTES
# ════════════════════════════════════════════════════════════
@app.route('/profile')
@login_required
def profile():
    if session['role'] == 'student':
        return redirect(url_for('student_profile'))
    uid  = session['user_id']
    user = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
    return render_template('profile.html', user=user)

@app.route('/notifications/read', methods=['POST'])
@login_required
def read_notifications():
    ex("UPDATE notifications SET is_read=1 WHERE user_id=?", (session['user_id'],))
    return jsonify({'ok': True})

@app.route('/notifications/count')
@login_required
def notif_count():
    c = q("SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND is_read=0",
          (session['user_id'],), one=True)['c']
    return jsonify({'count': c})


# ════════════════════════════════════════════════════════════
#  AI CHATBOT API
# ════════════════════════════════════════════════════════════
@app.route('/api/chatbot', methods=['POST'])
@login_required
def chatbot():
    msg    = request.json.get('message','').strip()
    events = q("SELECT * FROM events WHERE status='approved' ORDER BY date ASC")
    reply  = chatbot_response(msg, events)
    return jsonify({'reply': reply})


# ════════════════════════════════════════════════════════════
#  TEMPLATE FILTERS
# ════════════════════════════════════════════════════════════
@app.template_filter('fdate')
def fdate(v):
    try: return datetime.strptime(v,'%Y-%m-%d').strftime('%d %b %Y')
    except: return v

@app.template_filter('pct')
def pct(reg, total):
    return min(100, round((reg/total)*100)) if total else 0

@app.template_filter('from_json')
def from_json(v):
    try: return json.loads(v or '[]')
    except: return []

@app.template_filter('tags_str')
def tags_str(v):
    try: return ', '.join(json.loads(v or '[]'))
    except: return v or ''




# ════════════════════════════════════════════════════════════
#  QR CODE ROUTES
# ════════════════════════════════════════════════════════════
@app.route('/student/qr/<int:eid>')
@login_required
@role_required('student')
def student_qr(eid):
    uid = session['user_id']
    reg = q("SELECT * FROM registrations WHERE user_id=? AND event_id=?", (uid, eid), one=True)
    if not reg:
        flash('You are not registered for this event.', 'error')
        return redirect(url_for('my_registrations'))
    ev   = q("SELECT * FROM events WHERE id=?", (eid,), one=True)
    user = q("SELECT * FROM users WHERE id=?", (uid,), one=True)

    # Get or create QR token
    existing = q("SELECT * FROM qr_tokens WHERE user_id=? AND event_id=?", (uid, eid), one=True)
    if existing:
        token = existing['token']
    else:
        token = generate_qr_token(uid, eid)
        try:
            ex("INSERT INTO qr_tokens (user_id, event_id, token) VALUES (?,?,?)", (uid, eid, token))
        except:
            pass

    qr_data_url = generate_qr_svg(token, user['name'], ev['title'])
    return render_template('student/qr_ticket.html',
                           event=ev, user=user, token=token, qr_data_url=qr_data_url)


@app.route('/organizer/scan/<int:eid>', methods=['GET','POST'])
@login_required
@role_required('organizer')
def scan_qr(eid):
    event = q("SELECT * FROM events WHERE id=? AND organizer_id=?", (eid, session['user_id']), one=True)
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('org_dashboard'))
    result = None
    if request.method == 'POST':
        token = request.form.get('token','').strip()
        qr = q("SELECT * FROM qr_tokens WHERE token=? AND event_id=?", (token, eid), one=True)
        if not qr:
            result = {'ok': False, 'msg': '❌ Invalid QR token. Not registered for this event.'}
        elif qr['used']:
            user = q("SELECT name FROM users WHERE id=?", (qr['user_id'],), one=True)
            result = {'ok': False, 'msg': f'⚠️ Token already used by {user["name"]}. Possible duplicate scan.'}
        else:
            user = q("SELECT * FROM users WHERE id=?", (qr['user_id'],), one=True)
            ex("UPDATE qr_tokens SET used=1 WHERE id=?", (qr['id'],))
            ex("UPDATE registrations SET attended=1 WHERE user_id=? AND event_id=?", (qr['user_id'], eid))
            result = {'ok': True, 'msg': f'✅ Attendance marked for {user["name"]}!', 'user': dict(user)}
    regs = q("""SELECT r.*,u.name,u.email,qt.used as qr_used
                FROM registrations r JOIN users u ON r.user_id=u.id
                LEFT JOIN qr_tokens qt ON qt.user_id=r.user_id AND qt.event_id=r.event_id
                WHERE r.event_id=?""", (eid,))
    return render_template('organizer/scan_qr.html', event=event, result=result, registrations=regs)


# ════════════════════════════════════════════════════════════
#  VENUE AVAILABILITY CHECKER
# ════════════════════════════════════════════════════════════
@app.route('/organizer/venue-check', methods=['POST'])
@login_required
@role_required('organizer')
def venue_check():
    venue_id   = request.json.get('venue_id','')
    date       = request.json.get('date','')
    start_time = request.json.get('start_time','')
    end_time   = request.json.get('end_time','')
    exclude_id = request.json.get('exclude_id', None)
    if not all([venue_id, date, start_time]):
        return jsonify({'error': 'Missing fields'})
    result = check_venue_availability(venue_id, date, start_time, end_time, exclude_id)
    return jsonify(result)


# ════════════════════════════════════════════════════════════
#  AI EVENT TEMPLATE GENERATOR
# ════════════════════════════════════════════════════════════
@app.route('/organizer/generate-template', methods=['POST'])
@login_required
@role_required('organizer')
def generate_template():
    title    = request.json.get('title','').strip()
    category = request.json.get('category','Tech')
    fee      = float(request.json.get('fee', 0) or 0)
    if not title:
        return jsonify({'error': 'Title required'})
    template = generate_event_template(title, category, fee)
    return jsonify(template)


# ════════════════════════════════════════════════════════════
#  FEEDBACK ROUTES
# ════════════════════════════════════════════════════════════
@app.route('/student/feedback/<int:eid>', methods=['POST'])
@login_required
@role_required('student')
def submit_event_feedback(eid):
    uid     = session['user_id']
    rating  = int(request.form.get('rating', 3))
    comment = request.form.get('comment','').strip()
    try:
        ex("INSERT OR REPLACE INTO event_feedback (user_id,event_id,rating,comment) VALUES (?,?,?,?)",
           (uid, eid, rating, comment))
        flash('Thank you for your feedback! 🌟', 'success')
    except Exception as e:
        flash('Could not submit feedback.', 'error')
    return redirect(url_for('my_registrations'))


@app.route('/organizer/events/<int:eid>/feedback')
@login_required
@role_required('organizer')
def org_event_feedback(eid):
    event = q("SELECT * FROM events WHERE id=? AND organizer_id=?", (eid, session['user_id']), one=True)
    if not event:
        flash('Not found.', 'error')
        return redirect(url_for('org_dashboard'))
    feedbacks = q("""SELECT ef.*,u.name,u.department
        FROM event_feedback ef JOIN users u ON ef.user_id=u.id
        WHERE ef.event_id=? ORDER BY ef.created_at DESC""", (eid,))
    avg_rating = 0
    if feedbacks:
        avg_rating = round(sum(f['rating'] for f in feedbacks) / len(feedbacks), 1)
    return render_template('organizer/feedback.html', event=event,
                           feedbacks=feedbacks, avg_rating=avg_rating)


# ════════════════════════════════════════════════════════════
#  STUDENT CALENDAR ROUTE
# ════════════════════════════════════════════════════════════
@app.route('/student/calendar')
@login_required
@role_required('student')
def student_calendar():
    uid = session['user_id']
    # Get all approved events
    all_events = q("""SELECT e.*,v.name as venue_name,u.name as org_name,
                      SUM(CASE WHEN r2.user_id=? THEN 1 ELSE 0 END) as is_registered
                      FROM events e
                      LEFT JOIN venues v ON e.venue_id=v.id
                      LEFT JOIN users u ON e.organizer_id=u.id
                      LEFT JOIN registrations r2 ON e.id=r2.event_id
                      WHERE e.status='approved'
                      GROUP BY e.id ORDER BY e.date""", (uid,))
    # Build calendar data as JSON
    cal_events = []
    for ev in all_events:
        cal_events.append({
            'id':    ev['id'],
            'title': ev['title'],
            'date':  ev['date'],
            'time':  ev['time'],
            'category': ev['category'],
            'venue': ev['venue_name'] or 'TBD',
            'registered': bool(ev['is_registered']),
            'fee':   ev['registration_fee'] if ev['registration_fee'] else 0,
        })
    return render_template('student/calendar.html',
                           cal_events_json=json.dumps(cal_events))


@app.route('/organizer/venue-availability')
@login_required
@role_required('organizer')
def venue_availability():
    venues = q("SELECT * FROM venues ORDER BY name")
    return render_template('organizer/venue_availability.html', venues=venues)

if __name__ == '__main__':
    init_db()
    print("\n" + "="*55)
    print("  AI-Powered College Event Management System")
    print("="*55)
    print("  URL      : http://localhost:5000")
    print("  Admin    : admin@college.edu      / admin123")
    print("  Organizer: organizer@college.edu  / org123")
    print("  Student  : rohan@student.edu      / student123")
    print("="*55 + "\n")
    app.run(debug=True)
