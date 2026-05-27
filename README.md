# AI-Powered College Event Management System
### Python Flask · SQLite · Bootstrap · Rule-Based AI

---

## ABSTRACT

The AI-Powered College Event Management System (AI-CEMS) is a full-stack web application designed to digitalize and intelligently automate the management of college events. The system addresses limitations of traditional manual event coordination by providing a centralized, AI-enhanced platform with three user modules: Admin, Organizer, and Student.

Key AI capabilities include a content-based event recommendation engine, a rule-based attendance prediction model, a smart scheduling module that detects venue/time conflicts, and an intent-based chatbot assistant. The system is built with Python Flask, SQLite (MySQL-compatible schema), and Bootstrap-enhanced HTML/CSS templates.

---

## 1. SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                          │
│         HTML5 + CSS3 + Bootstrap + JavaScript               │
│     Admin UI | Organizer UI | Student UI | Chatbot UI       │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP Requests
┌────────────────────────▼────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│              Python Flask (MVC Architecture)                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Admin   │  │Organizer │  │ Student  │  │Chatbot   │   │
│  │ Routes   │  │ Routes   │  │ Routes   │  │  API     │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                    Jinja2 Template Engine                    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                      AI ENGINE LAYER                         │
│  ┌───────────────┐  ┌────────────────┐  ┌────────────────┐ │
│  │ Recommendation│  │ Attendance     │  │ Smart          │ │
│  │ Engine        │  │ Prediction     │  │ Scheduler      │ │
│  │(Content-Based)│  │(Rule-Based ML) │  │(Conflict Check)│ │
│  └───────────────┘  └────────────────┘  └────────────────┘ │
│  ┌───────────────────────────────────────────────────────┐  │
│  │           Intent-Based Chatbot (NLU Engine)           │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                      DATA LAYER                              │
│          SQLite Database (MySQL-Compatible Schema)           │
│   users | events | venues | registrations | activity_log    │
│                    + notifications                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. DATABASE SCHEMA

### Tables & Relationships

```sql
-- USERS TABLE
CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    password    TEXT NOT NULL,            -- SHA-256 hashed
    role        TEXT DEFAULT 'student',   -- admin | organizer | student
    department  TEXT,
    year        TEXT,
    reg_no      TEXT,
    interests   TEXT DEFAULT '[]',        -- JSON array of interest tags
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

-- VENUES TABLE
CREATE TABLE venues (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    capacity    INTEGER NOT NULL,
    location    TEXT,
    facilities  TEXT
);

-- EVENTS TABLE
CREATE TABLE events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    category         TEXT NOT NULL,       -- Tech|Cultural|Sports|Workshop|Music|Art
    description      TEXT,
    date             TEXT NOT NULL,
    time             TEXT NOT NULL,
    end_time         TEXT,
    venue_id         INTEGER,
    organizer_id     INTEGER NOT NULL,
    max_participants INTEGER DEFAULT 100,
    status           TEXT DEFAULT 'pending', -- pending|approved|rejected
    tags             TEXT DEFAULT '[]',   -- JSON array for AI recommendations
    created_at       TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(venue_id)     REFERENCES venues(id),
    FOREIGN KEY(organizer_id) REFERENCES users(id)
);

-- REGISTRATIONS TABLE
CREATE TABLE registrations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    event_id      INTEGER NOT NULL,
    registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
    attended      INTEGER DEFAULT 0,      -- 0=no, 1=yes
    feedback      TEXT,
    rating        INTEGER,                -- 1-5 stars
    UNIQUE(user_id, event_id),
    FOREIGN KEY(user_id)  REFERENCES users(id),
    FOREIGN KEY(event_id) REFERENCES events(id)
);

-- ACTIVITY LOG TABLE
CREATE TABLE activity_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER,
    action    TEXT NOT NULL,
    details   TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

-- NOTIFICATIONS TABLE
CREATE TABLE notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    message    TEXT NOT NULL,
    is_read    INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
```

### ER Diagram (Textual Description)

```
USERS ──────────────────────────────────────────────────────
  │ id (PK), name, email, password, role, department,       
  │ year, reg_no, interests, created_at                     
  │                                                          
  ├─[1:N]──► EVENTS (organizer_id → users.id)              
  │             id, title, category, date, time, end_time,  
  │             venue_id, organizer_id, max_participants,    
  │             status, tags                                 
  │             │                                           
  │             └─[N:1]──► VENUES (venue_id → venues.id)   
  │                          id, name, capacity, location    
  │                                                          
  ├─[1:N]──► REGISTRATIONS (user_id → users.id)            
  │             id, user_id, event_id, attended, feedback,   
  │             rating, registered_at                        
  │             │                                           
  │             └─[N:1]──► EVENTS (event_id → events.id)   
  │                                                          
  ├─[1:N]──► ACTIVITY_LOG (user_id → users.id)             
  │             id, action, details, timestamp              
  │                                                          
  └─[1:N]──► NOTIFICATIONS (user_id → users.id)            
               id, message, is_read, created_at             
```

**Relationships:**
- A `User` (organizer) can create many `Events` — **One-to-Many**
- An `Event` is held at one `Venue` — **Many-to-One**
- A `Student` can register for many `Events` — **Many-to-Many** (via `registrations`)
- A `User` can have many `Notifications` — **One-to-Many**
- A `User` generates many `ActivityLog` entries — **One-to-Many**

---

## 3. AI FEATURES

### 3.1 Event Recommendation System
- **Type:** Content-Based Filtering
- **Logic:** Matches student interest tags against event tags using overlap scoring
- **Boost:** Events happening within 14 days get +0.2 score boost
- **Output:** Top-N recommended events not yet registered by the student

### 3.2 Attendance Prediction
- **Type:** Rule-Based ML simulation (heuristic model)
- **Inputs:** Category, registration fill rate, day of week, historical base rates
- **Base rates:** Workshop 85%, Tech 78%, Sports 70%, Cultural 65%, Music 60%, Art 55%
- **Output:** Predicted attendance rate (%), expected headcount, level (High/Moderate/Low), and actionable insight

### 3.3 Smart Scheduling (Conflict Detection)
- **Type:** Rule-based constraint satisfaction
- **Logic:** Checks time overlap between new event and existing approved events at the same venue
- **Output:** Warning message with conflicting event details, prevents submission

### 3.4 AI Chatbot
- **Type:** Intent-based NLU (keyword matching)
- **Intents:** greeting, events, register, help, venue, category, date, thanks, bye, fuzzy-search
- **Responses:** Dynamic — pulls live event data from DB for accurate answers

---

## 4. PROJECT STRUCTURE

```
ai_cems/
├── app.py                    ← Main Flask app (all routes)
├── cems.db                   ← SQLite database (auto-created)
├── ai/
│   ├── __init__.py
│   └── engine.py             ← AI engine (all 4 AI modules)
├── templates/
│   ├── base.html             ← Master layout (nav, sidebar, chatbot)
│   ├── profile.html          ← Shared profile
│   ├── auth/
│   │   ├── login.html        ← Login page
│   │   └── register.html     ← Student registration
│   ├── admin/
│   │   ├── dashboard.html    ← Stats, pending approvals, activity
│   │   ├── events.html       ← All events management table
│   │   ├── users.html        ← User management
│   │   ├── venues.html       ← Venue listing
│   │   └── reports.html      ← Analytics & reports
│   ├── organizer/
│   │   ├── dashboard.html    ← My events, stats, notifications
│   │   ├── event_form.html   ← Create/edit event (AI conflict check)
│   │   └── registrations.html ← Participant list + AI attendance
│   └── student/
│       ├── events.html       ← Browse + AI recommendations
│       ├── my_events.html    ← Registered events + feedback
│       └── profile.html      ← Profile + participation history
└── README.md                 ← This file
```

---

## 5. HOW TO RUN

```bash
# Step 1: Install Flask
pip install flask

# Step 2: Navigate to project
cd ai_cems

# Step 3: Run
python app.py

# Open: http://localhost:5000
```

### Demo Credentials

| Role      | Email                    | Password    |
|-----------|--------------------------|-------------|
| Admin     | admin@college.edu        | admin123    |
| Organizer | organizer@college.edu    | org123      |
| Student   | rohan@student.edu        | student123  |

---

## 6. MODULES OVERVIEW

### Admin Module
- Dashboard with 6 key stats, live activity log, category analytics
- Event approval / rejection with organizer notifications
- User management (view, filter by role, delete)
- Venue management
- Reports: top events, department registrations, attendance rates

### Organizer Module
- Dashboard with personal event stats and notifications
- Create events with AI conflict detection
- Edit/delete events
- View participant lists with AI attendance prediction
- Mark attendance for each student

### Student Module
- Browse events with search & category filter
- AI-powered personalized event recommendations panel
- One-click registration with seat tracking
- My Events page with attendance status and star ratings
- Participation history profile page
- AI chatbot for event queries (floating button)

---

## 7. TECHNOLOGIES USED

| Layer       | Technology                                    |
|-------------|-----------------------------------------------|
| Backend     | Python 3.12, Flask 3.x                        |
| Database    | SQLite3 (MySQL-compatible schema)             |
| Frontend    | HTML5, CSS3, Bootstrap-inspired custom CSS    |
| Templating  | Jinja2                                        |
| Auth        | Flask Sessions + SHA-256 password hashing     |
| AI Engine   | Python (rule-based, no external ML library)   |
| Fonts       | Google Fonts (Fraunces, Plus Jakarta Sans)    |

---

## 8. CONCLUSION

The AI-Powered College Event Management System successfully digitalizes the entire event lifecycle — from creation and approval to registration and post-event feedback. The system brings measurable benefits:

- **Efficiency:** Eliminates manual paperwork and reduces coordination overhead
- **Intelligence:** AI recommendations increase event discovery and student engagement
- **Reliability:** Conflict detection prevents double-booking of venues
- **Insight:** Attendance prediction helps organizers plan resources better
- **Accessibility:** 24/7 chatbot support reduces administrative queries

The three-module architecture (Admin, Organizer, Student) provides clear role-based separation of concerns, ensuring security and usability at each level.

---

## 9. FUTURE ENHANCEMENTS

1. **Machine Learning Upgrade** — Replace rule-based AI with scikit-learn models (collaborative filtering, gradient boosting for attendance prediction)
2. **Email Notifications** — Automated reminders via SMTP/SendGrid
3. **QR Code Attendance** — Generate QR tickets; scan at entry for instant attendance marking
4. **Calendar Integration** — Export events to Google Calendar / iCal
5. **Mobile App** — React Native or Flutter app using Flask REST API
6. **Advanced Analytics** — Real-time charts with Chart.js or Plotly
7. **Payment Gateway** — Razorpay/Stripe for paid event tickets
8. **Multi-college Support** — Multi-tenant architecture for university networks
9. **Social Features** — Event sharing, comments, peer-to-peer recommendations
10. **Natural Language Processing** — Upgrade chatbot with transformer-based model (BERT/GPT)
11. **MySQL Migration** — Replace SQLite with MySQL for production scalability
12. **Docker Deployment** — Containerize with Docker + Nginx for cloud hosting
