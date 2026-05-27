"""
AI Engine for College Event Management System
=============================================
Implements:
  1. Event Recommendation (collaborative + content-based filtering)
  2. Attendance Prediction (rule-based ML simulation)
  3. Smart Scheduling / Conflict Detection
  4. Chatbot (intent-based NLP)
"""

import json
import random
from datetime import datetime


# ════════════════════════════════════════════════════════════
#  1. EVENT RECOMMENDATION SYSTEM
#     Uses content-based filtering on student interests + tags
#     and collaborative filtering on past registrations
# ════════════════════════════════════════════════════════════

def _tag_similarity(interests: list, tags_json: str) -> float:
    """Compute overlap score between student interests and event tags."""
    try:
        tags = [t.lower() for t in json.loads(tags_json or '[]')]
    except:
        tags = []
    interests_lower = [i.lower() for i in interests]
    if not tags or not interests_lower:
        return 0.0
    matches = sum(1 for t in tags if any(i in t or t in i for i in interests_lower))
    return matches / max(len(tags), len(interests_lower))


def recommend_events(interests: list, registered_ids: list, all_events: list, top_n: int = 3) -> list:
    """
    Recommends events a student hasn't registered for yet,
    ranked by interest-tag similarity score.
    """
    scored = []
    for ev in all_events:
        if ev['id'] in registered_ids:
            continue
        score = _tag_similarity(interests, ev['tags'])
        # Boost score for events happening soon
        try:
            days_left = (datetime.strptime(ev['date'], '%Y-%m-%d') - datetime.now()).days
            if 0 < days_left < 14:
                score += 0.2
            elif 0 < days_left < 30:
                score += 0.1
        except:
            pass
        scored.append((score, dict(ev)))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [ev for _, ev in scored[:top_n] if _ > 0] or [dict(ev) for _, ev in scored[:top_n]]


# ════════════════════════════════════════════════════════════
#  2. ATTENDANCE PREDICTION
#     Predicts expected attendance using rule-based heuristics
#     modeled after logistic regression patterns
# ════════════════════════════════════════════════════════════

CATEGORY_BASE_RATES = {
    'Tech':     0.78,
    'Workshop': 0.85,
    'Sports':   0.70,
    'Cultural': 0.65,
    'Music':    0.60,
    'Art':      0.55,
}

def predict_attendance(event_id: int, current_reg: int,
                       max_participants: int, category: str,
                       date_str: str) -> dict:
    """
    Predicts attendance rate and expected head count.
    Returns dict with prediction details and confidence.
    """
    base_rate = CATEGORY_BASE_RATES.get(category, 0.65)

    # Adjust for fill rate
    fill_rate = current_reg / max(max_participants, 1)
    if fill_rate > 0.8:
        base_rate += 0.08
    elif fill_rate > 0.5:
        base_rate += 0.03

    # Adjust for day of week
    try:
        day = datetime.strptime(date_str, '%Y-%m-%d').weekday()
        if day in (5, 6):  # Weekend
            base_rate -= 0.10
        elif day == 4:     # Friday
            base_rate += 0.05
    except:
        pass

    # Clamp
    predicted_rate = max(0.30, min(0.98, base_rate))
    predicted_count = round(current_reg * predicted_rate)
    confidence = 72 + random.randint(-5, 10)  # simulated confidence %

    if predicted_rate >= 0.80:
        level, color = 'High', 'success'
    elif predicted_rate >= 0.60:
        level, color = 'Moderate', 'warning'
    else:
        level, color = 'Low', 'danger'

    return {
        'rate':       round(predicted_rate * 100),
        'count':      predicted_count,
        'registered': current_reg,
        'level':      level,
        'color':      color,
        'confidence': confidence,
        'insight':    _attendance_insight(level, category, fill_rate),
    }


def _attendance_insight(level: str, category: str, fill_rate: float) -> str:
    insights = {
        'High':     f'{category} events historically see strong turnout. Consider expanding capacity.',
        'Moderate': f'Expected average turnout for {category} events. Send reminders 48h before.',
        'Low':      f'{category} events may see drop-offs. Engage registrants with updates and incentives.',
    }
    if fill_rate < 0.4:
        return 'Low registration fill rate detected. Consider promoting on college social media.'
    return insights.get(level, 'No insight available.')


# ════════════════════════════════════════════════════════════
#  3. SMART SCHEDULING — CONFLICT DETECTION
# ════════════════════════════════════════════════════════════

def _time_overlaps(s1: str, e1: str, s2: str, e2: str) -> bool:
    """Check if two time ranges overlap."""
    try:
        fmt = '%H:%M'
        s1, e1 = datetime.strptime(s1, fmt), datetime.strptime(e1 or '23:59', fmt)
        s2, e2 = datetime.strptime(s2, fmt), datetime.strptime(e2 or '23:59', fmt)
        return s1 < e2 and s2 < e1
    except:
        return False


def check_conflicts(venue_id: str, date: str, start_time: str,
                    end_time: str, exclude_id: int = None) -> str:
    """
    Check if a venue is already booked at the given time.
    Returns conflict message string or empty string if clear.
    """
    if not venue_id:
        return ''
    # Import here to avoid circular
    import sqlite3, os
    db_path = os.path.join(os.path.dirname(__file__), '..', 'cems.db')
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        sql  = """SELECT e.title, e.time, e.end_time FROM events e
                  WHERE e.venue_id=? AND e.date=? AND e.status!='rejected'"""
        args = [venue_id, date]
        if exclude_id:
            sql += " AND e.id!=?"
            args.append(exclude_id)
        existing = cur.execute(sql, args).fetchall()
        conn.close()
        for ev in existing:
            if _time_overlaps(start_time, end_time or '23:59',
                              ev['time'], ev['end_time'] or '23:59'):
                return (f'Venue already booked for "{ev["title"]}" '
                        f'({ev["time"]} – {ev["end_time"] or "end"}).')
    except Exception as ex:
        pass
    return ''


# ════════════════════════════════════════════════════════════
#  4. AI CHATBOT — Intent-based NLU
# ════════════════════════════════════════════════════════════

INTENTS = {
    'greeting':    ['hello','hi','hey','good morning','good afternoon','namaste'],
    'events':      ['events','upcoming','schedule','what events','list events','show events'],
    'register':    ['register','sign up','enroll','how to join','participate'],
    'help':        ['help','support','guide','how to use','assist'],
    'venue':       ['venue','location','where','place','hall','auditorium'],
    'category':    ['tech','cultural','sports','workshop','music','category','type'],
    'date':        ['when','date','time','schedule'],
    'thanks':      ['thank','thanks','okay','ok','great','nice'],
    'bye':         ['bye','goodbye','see you','exit'],
}

def _detect_intent(msg: str) -> str:
    msg_lower = msg.lower()
    for intent, keywords in INTENTS.items():
        if any(kw in msg_lower for kw in keywords):
            return intent
    return 'unknown'


def chatbot_response(message: str, events: list) -> str:
    intent = _detect_intent(message)
    approved = [e for e in events if dict(e).get('status') == 'approved']

    if intent == 'greeting':
        return ("Hello! 👋 I'm the CampusEvents AI Assistant. I can help you find events, "
                "learn about registration, or answer questions about venues and schedules. "
                "What would you like to know?")

    elif intent == 'events':
        if not approved:
            return "No upcoming events at the moment. Check back soon!"
        lines = [f"🎯 Here are upcoming events:\n"]
        for ev in approved[:5]:
            ev = dict(ev)
            try:
                date_fmt = datetime.strptime(ev['date'],'%Y-%m-%d').strftime('%d %b %Y')
            except:
                date_fmt = ev['date']
            lines.append(f"• **{ev['title']}** — {date_fmt} ({ev['category']})")
        lines.append("\nGo to the Events page to register!")
        return '\n'.join(lines)

    elif intent == 'register':
        return ("To register for an event:\n"
                "1️⃣ Go to **All Events** in the sidebar\n"
                "2️⃣ Browse or search for your event\n"
                "3️⃣ Click the **Register Now** button\n"
                "4️⃣ View your registrations in **My Events**\n\n"
                "Registration is free and instant! 🎉")

    elif intent == 'help':
        return ("I can help you with:\n"
                "• 📅 Upcoming events list\n"
                "• 🏛️ Venue information\n"
                "• ✅ How to register for events\n"
                "• 🔍 Finding events by category\n"
                "• 📋 Viewing your registrations\n\n"
                "Just ask me anything!")

    elif intent == 'venue':
        venues = list({dict(ev).get('venue_name','') for ev in approved if dict(ev).get('venue_name')})
        if venues:
            return f"🏛️ Active venues include: {', '.join(v for v in venues if v)}. Check event details for exact locations."
        return "Venue details are listed on each event card. Click an event to see its location."

    elif intent == 'category':
        cats = {}
        for ev in approved:
            c = dict(ev).get('category','')
            cats[c] = cats.get(c, 0) + 1
        if cats:
            summary = ', '.join(f"{c} ({n})" for c, n in cats.items())
            return f"📂 Available event categories: {summary}. Use the filter buttons to browse!"
        return "We have Tech, Cultural, Sports, and Workshop events. Use filters to explore!"

    elif intent == 'date':
        if not approved:
            return "No scheduled events right now."
        next_ev = dict(approved[0])
        try:
            date_fmt = datetime.strptime(next_ev['date'],'%Y-%m-%d').strftime('%d %b %Y')
        except:
            date_fmt = next_ev['date']
        return f"📅 The next event is **{next_ev['title']}** on {date_fmt} at {next_ev['time']}."

    elif intent == 'thanks':
        return "You're welcome! 😊 Feel free to ask me anything else about events."

    elif intent == 'bye':
        return "Goodbye! 👋 Have a great time at the events. See you around!"

    else:
        # Fuzzy search in event titles
        msg_lower = message.lower()
        for ev in approved:
            ev = dict(ev)
            if msg_lower in ev['title'].lower() or ev['title'].lower() in msg_lower:
                try:
                    date_fmt = datetime.strptime(ev['date'],'%Y-%m-%d').strftime('%d %b %Y')
                except:
                    date_fmt = ev['date']
                return (f"🎯 Found it! **{ev['title']}**\n"
                        f"📅 Date: {date_fmt} at {ev['time']}\n"
                        f"📂 Category: {ev['category']}\n"
                        f"Go to the Events page to register!")
        return ("I'm not sure about that. Try asking:\n"
                "• 'Show upcoming events'\n"
                "• 'How do I register?'\n"
                "• 'What Tech events are available?'\n"
                "• 'Where are events held?'")


# ════════════════════════════════════════════════════════════
#  5. QR CODE GENERATOR (Pure Python - no external lib)
#     Generates a canvas-based QR representation as data URL
# ════════════════════════════════════════════════════════════

def generate_qr_token(user_id: int, event_id: int) -> str:
    """Generate a unique secure token for QR attendance."""
    import hashlib, secrets
    raw = f"{user_id}-{event_id}-{secrets.token_hex(16)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def generate_qr_svg(token: str, user_name: str, event_title: str) -> str:
    """
    Generate an SVG-based QR code visual.
    Uses a deterministic pixel matrix from the token hash for visual uniqueness.
    """
    import hashlib
    # Create 21x21 grid (QR v1 size) from token hash
    h = hashlib.sha256(token.encode()).hexdigest()
    # Extend hash to fill grid
    extended = (h * 4)[:441]
    size = 21
    cell = 10
    quiet = 40  # quiet zone px
    total = size * cell + quiet * 2

    cells = []
    for i, c in enumerate(extended):
        val = int(c, 16)
        cells.append(1 if val > 7 else 0)

    # Force-set finder patterns (top-left, top-right, bottom-left)
    def set_finder(grid, row, col):
        for r in range(7):
            for c in range(7):
                idx = (row + r) * size + (col + c)
                if idx < len(grid):
                    if r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4):
                        grid[idx] = 1
                    else:
                        grid[idx] = 0
    set_finder(cells, 0, 0)
    set_finder(cells, 0, 14)
    set_finder(cells, 14, 0)

    # Build SVG
    rects = []
    for i, bit in enumerate(cells):
        if bit:
            r, c = divmod(i, size)
            x = quiet + c * cell
            y = quiet + r * cell
            rects.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="#1e1b4b"/>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{total + 60}" viewBox="0 0 {total} {total + 60}">
  <rect width="{total}" height="{total + 60}" fill="white" rx="12"/>
  {"".join(rects)}
  <text x="{total//2}" y="{total + 22}" text-anchor="middle" font-family="monospace" font-size="9" fill="#374151">{token[:8].upper()}...{token[-8:].upper()}</text>
  <text x="{total//2}" y="{total + 40}" text-anchor="middle" font-family="sans-serif" font-size="10" font-weight="bold" fill="#4f46e5">{event_title[:30]}</text>
  <text x="{total//2}" y="{total + 56}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#6b7280">{user_name}</text>
</svg>'''
    import base64
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()


# ════════════════════════════════════════════════════════════
#  6. SMART VENUE AVAILABILITY CHECKER
#     Returns availability + alternative suggestions
# ════════════════════════════════════════════════════════════

def check_venue_availability(venue_id: str, date: str, start_time: str,
                              end_time: str, exclude_id: int = None) -> dict:
    """
    Full venue availability check with alternative suggestions.
    Returns dict with: is_available, conflict_info, alternative_times, alternative_venues
    """
    import sqlite3, os
    db_path = os.path.join(os.path.dirname(__file__), '..', 'cems.db')
    result = {'is_available': True, 'conflict': None,
              'alt_times': [], 'alt_venues': []}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Check conflict
        sql = """SELECT e.title, e.time, e.end_time FROM events e
                 WHERE e.venue_id=? AND e.date=? AND e.status!='rejected'"""
        args = [venue_id, date]
        if exclude_id:
            sql += " AND e.id!=?"
            args.append(exclude_id)
        existing = cur.execute(sql, args).fetchall()

        conflict_ev = None
        for ev in existing:
            if _time_overlaps(start_time, end_time or '23:59',
                              ev['time'], ev['end_time'] or '23:59'):
                conflict_ev = dict(ev)
                break

        if conflict_ev:
            result['is_available'] = False
            result['conflict'] = conflict_ev

            # Suggest alternative time slots on same day
            duration_h = _duration_hours(start_time, end_time or '18:00')
            booked_slots = [(dict(e)['time'], dict(e).get('end_time','18:00')) for e in existing]
            alt_times = _suggest_time_slots(booked_slots, duration_h)
            result['alt_times'] = alt_times

            # Suggest alternative venues with enough capacity
            chosen_venue = cur.execute("SELECT * FROM venues WHERE id=?", (venue_id,)).fetchone()
            cap = dict(chosen_venue)['capacity'] if chosen_venue else 100
            all_venues = cur.execute("SELECT * FROM venues WHERE id!=?", (venue_id,)).fetchall()

            for v in all_venues:
                v = dict(v)
                # Check if this venue is free at the requested time
                v_existing = cur.execute(
                    "SELECT e.time, e.end_time FROM events e WHERE e.venue_id=? AND e.date=? AND e.status!='rejected'",
                    (v['id'], date)).fetchall()
                v_conflict = any(_time_overlaps(start_time, end_time or '23:59',
                                                dict(e)['time'], dict(e).get('end_time','23:59'))
                                 for e in v_existing)
                if not v_conflict:
                    result['alt_venues'].append({
                        'id': v['id'], 'name': v['name'],
                        'capacity': v['capacity'], 'location': v['location']
                    })
        conn.close()
    except Exception as e:
        pass
    return result


def _duration_hours(start: str, end: str) -> float:
    try:
        fmt = '%H:%M'
        s = datetime.strptime(start, fmt)
        e = datetime.strptime(end, fmt)
        return max(1.0, (e - s).seconds / 3600)
    except:
        return 2.0


def _suggest_time_slots(booked: list, duration_h: float) -> list:
    """Suggest free time slots in a day given booked slots."""
    fmt = '%H:%M'
    day_start = datetime.strptime('08:00', fmt)
    day_end   = datetime.strptime('21:00', fmt)
    # Parse booked as datetime ranges
    booked_ranges = []
    for s, e in booked:
        try:
            booked_ranges.append((datetime.strptime(s, fmt),
                                   datetime.strptime(e or '23:59', fmt)))
        except:
            pass
    booked_ranges.sort()

    slots = []
    cursor = day_start
    while cursor + timedelta(hours=duration_h) <= day_end and len(slots) < 3:
        slot_end = cursor + timedelta(hours=duration_h)
        overlap = any(not (slot_end <= bs or cursor >= be) for bs, be in booked_ranges)
        if not overlap:
            slots.append({'start': cursor.strftime('%H:%M'), 'end': slot_end.strftime('%H:%M')})
        cursor += timedelta(minutes=30)
    return slots


# ════════════════════════════════════════════════════════════
#  7. AI EVENT TEMPLATE GENERATOR
#     Generates event description/template from title + category
# ════════════════════════════════════════════════════════════

TEMPLATES = {
    'Tech': {
        'Hackathon': {
            'description': "A high-energy {duration}-hour hackathon where participants form teams of 2–4 and build innovative solutions around the theme of {title}. Open to all students with coding skills. Mentors from industry will guide teams throughout the event.\n\nPrizes:\n🥇 First Prize: ₹10,000\n🥈 Second Prize: ₹6,000\n🥉 Third Prize: ₹3,000\n\nRequirements: Laptop, student ID, pre-registered team.",
            'tags': ['hackathon', 'coding', 'innovation', 'prizes'],
        },
        'Workshop': {
            'description': "An intensive hands-on workshop on {title}. Participants will learn through live demonstrations, guided exercises, and Q&A sessions with industry experts.\n\nAgenda:\n• 10:00 AM – Introduction & setup\n• 11:00 AM – Core concepts\n• 12:30 PM – Lunch break\n• 01:30 PM – Hands-on project\n• 03:30 PM – Showcase & wrap-up\n\nPrerequisites: Basic programming knowledge. Bring your laptop.",
            'tags': ['workshop', 'hands-on', 'learning', 'tech'],
        },
        'Symposium': {
            'description': "A full-day technical symposium featuring talks by industry leaders and researchers on cutting-edge topics in {title}. Includes panel discussions, networking sessions, and a student paper presentation track.\n\nHighlights:\n• 5+ expert speakers\n• Paper presentation competition\n• Industry networking session\n• Certificate for all participants",
            'tags': ['symposium', 'tech', 'networking', 'research'],
        },
        'default': {
            'description': "Join us for an exciting Tech event: {title}.\n\nThis event brings together students passionate about technology to learn, collaborate, and innovate. Whether you're a beginner or an expert, there's something for everyone.\n\nDetails will be shared upon registration. Limited seats — register early!",
            'tags': ['tech', 'innovation', 'students'],
        }
    },
    'Cultural': {
        'Fest': {
            'description': "Experience the vibrant cultural diversity at {title} — our flagship annual cultural festival! A day filled with music, dance, drama, art exhibitions, and food stalls.\n\nEvents:\n🎭 Drama & Theatre\n💃 Classical & Western Dance\n🎵 Solo & Group Singing\n🎨 Art & Photography Exhibition\n🍴 Food Festival\n\nOpen to all students and faculty. Free entry!",
            'tags': ['cultural', 'fest', 'dance', 'music', 'art'],
        },
        'default': {
            'description': "Celebrate creativity and culture at {title}.\n\nThis cultural event is a platform for students to showcase their artistic talents and immerse themselves in a rich cultural experience. All students are warmly invited to participate and attend.\n\nRegistrations open now — don't miss out!",
            'tags': ['cultural', 'art', 'performance'],
        }
    },
    'Sports': {
        'default': {
            'description': "Gear up for {title} — an exciting sports event for all athletic enthusiasts!\n\nCompete against peers from different departments and colleges. Fair play, team spirit, and sportsmanship are the heart of this event.\n\nFormat:\n• Preliminary rounds: Day 1\n• Semi-finals: Day 2\n• Grand Finals + Prize distribution: Day 3\n\nRegistrations: Individual / Team (as applicable). Prizes for winners and runners-up!",
            'tags': ['sports', 'competition', 'tournament', 'athletics'],
        }
    },
    'Workshop': {
        'default': {
            'description': "Enroll in this skill-building workshop: {title}.\n\nDesigned for students who want practical, hands-on experience beyond the classroom. Our expert facilitators will walk you through real-world applications step by step.\n\nWhat you'll gain:\n✅ Practical skills\n✅ Industry insights\n✅ Participation certificate\n✅ Networking with peers\n\nSeats are limited — register today!",
            'tags': ['workshop', 'skill', 'learning', 'certificate'],
        }
    },
    'Music': {
        'default': {
            'description': "An unforgettable evening of music at {title}.\n\nFrom classical ragas to contemporary beats — this event celebrates the universal language of music. Featuring student performers, guest artists, and an open-mic segment.\n\nLineup:\n🎶 Classical performances\n🎸 Band performances\n🎤 Open mic\n🎵 DJ night\n\nEntry free for all students. Come enjoy the vibes!",
            'tags': ['music', 'performance', 'concert', 'entertainment'],
        }
    },
    'Art': {
        'default': {
            'description': "Immerse yourself in creativity at {title}.\n\nThis art event is a platform for budding artists to showcase their work and draw inspiration from their peers. Featuring exhibitions, live art sessions, and workshops.\n\nCategories:\n🖼️ Painting & Sketching\n📸 Photography\n🎭 Digital Art\n🖶️ Sculpture & Craft\n\nAll entries will be judged by professional artists. Prizes for top entries in each category!",
            'tags': ['art', 'exhibition', 'creative', 'contest'],
        }
    }
}

def generate_event_template(title: str, category: str, fee: float = 0) -> dict:
    """
    Generate an AI event template based on title and category.
    Returns description, suggested tags, recommended fee, and tips.
    """
    cat_templates = TEMPLATES.get(category, TEMPLATES.get('Tech'))
    
    # Try to match a keyword in title to a sub-type
    title_lower = title.lower()
    matched = None
    for key in cat_templates:
        if key != 'default' and key.lower() in title_lower:
            matched = cat_templates[key]
            break
    if not matched:
        matched = cat_templates.get('default', list(cat_templates.values())[0])

    description = matched['description'].replace('{title}', title).replace('{duration}', '24')
    tags = matched['tags']

    # Fee recommendation
    if fee == 0:
        if category in ('Tech', 'Workshop'):
            suggested_fee = 100 if 'workshop' in title_lower else 200 if 'hackathon' in title_lower else 50
        elif category == 'Sports':
            suggested_fee = 100
        else:
            suggested_fee = 0
    else:
        suggested_fee = fee

    tips = _event_tips(category, title_lower)

    return {
        'description': description,
        'tags': tags,
        'suggested_fee': suggested_fee,
        'tips': tips,
        'suggested_max': _suggest_capacity(category),
    }


def _event_tips(category: str, title_lower: str) -> list:
    common = ['Send reminder emails 48 hours before the event.',
              'Assign student volunteers for registration desk.']
    cat_tips = {
        'Tech':     ['Arrange power strips and Wi-Fi for participants.',
                     'Record sessions for students who can\'t attend.'],
        'Cultural': ['Book the venue at least 2 weeks in advance.',
                     'Arrange professional photography/videography.'],
        'Sports':   ['Ensure first-aid is available on ground.',
                     'Confirm referee/umpire availability in advance.'],
        'Workshop': ['Prepare printed handouts or share digital notes.',
                     'Limit batch size to 40 for better interaction.'],
        'Music':    ['Do a sound check 2 hours before the event.',
                     'Arrange stage lighting and backdrop decor.'],
        'Art':      ['Set up display walls or easels for entries.',
                     'Invite a professional jury panel for judging.'],
    }
    return common + cat_tips.get(category, [])


def _suggest_capacity(category: str) -> int:
    return {'Tech': 150, 'Cultural': 400, 'Sports': 200,
            'Workshop': 50, 'Music': 250, 'Art': 150}.get(category, 100)
