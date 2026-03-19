from flask import Flask, request, render_template, session, jsonify, redirect, url_for
from openai import OpenAI, RateLimitError
from dotenv import load_dotenv
import os
import uuid
import json
import time
import io

import database as db

load_dotenv()

APP_ROOT = os.environ.get('APP_ROOT', os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(APP_ROOT, 'templates'),
    static_folder=os.path.join(APP_ROOT, 'static'),
)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', uuid.uuid4().hex)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY', 'placeholder'))

try:
    db.init_db()
except Exception:
    pass


def get_user_id():
    if 'user_id' not in session:
        session['user_id'] = uuid.uuid4().hex
    return session['user_id']


def build_profile_context(user):
    parts = []
    if user.get('resume_text'):
        parts.append(f"RESUME:\n{user['resume_text'][:3000]}")
    if user.get('target_role'):
        parts.append(f"TARGET ROLE: {user['target_role']}")
    if user.get('timeline'):
        parts.append(f"TIMELINE: {user['timeline']}")
    if user.get('work_preference'):
        parts.append(f"WORK PREFERENCE: {user['work_preference']}")
    if user.get('interests'):
        parts.append(f"INTERESTS: {user['interests']}")
    if user.get('education'):
        parts.append(f"EDUCATION: {user['education']}")
    return "\n\n".join(parts) if parts else ""


def extract_text_from_file(file_storage):
    """Extract text from uploaded PDF, DOCX, or TXT files."""
    filename = file_storage.filename or ''
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    try:
        if ext == 'pdf':
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(file_storage.read()))
            return "\n".join(page.extract_text() or '' for page in reader.pages).strip()

        elif ext in ('docx', 'doc'):
            from docx import Document
            doc = Document(io.BytesIO(file_storage.read()))
            return "\n".join(p.text for p in doc.paragraphs).strip()

        elif ext == 'txt':
            return file_storage.read().decode('utf-8', errors='ignore').strip()
    except ImportError:
        return ''

    return ''


SYSTEM_PROMPT = """You are Aptigenic, an elite AI career strategist — not a generic chatbot.

You have deep context about this user (provided below). Use it in EVERY response.
Never ask for information you already have. Be specific, not generic.

Your personality:
- Direct, warm, and actionable — like a brilliant friend who happens to be a career expert
- You give concrete next steps, not vague advice
- You reference specific details from their background
- You think in terms of ROI: time invested vs career impact

Your capabilities:
- Career path analysis with timelines, salaries, and risk levels
- Skill gap identification with specific learning plans
- Resume and interview strategy
- Networking tactics with specific outreach templates
- Market intelligence and trend analysis

Formatting rules:
- Use **bold** for key terms and career titles
- Use bullet points and numbered lists for clarity
- Use headers (##) to organize longer responses
- Keep responses focused and scannable

If the user hasn't completed onboarding yet, warmly encourage them to do so for personalized advice.
""".strip()


# ─── Pages ────────────────────────────────────────────────────

@app.route('/')
def welcome():
    return render_template('welcome.html')


@app.route('/onboard')
def onboard():
    uid = get_user_id()
    user = db.get_or_create_user(uid)
    return render_template('onboard.html', user=user)


@app.route('/dashboard')
def dashboard():
    uid = get_user_id()
    user = db.get_user(uid)
    if not user or not user.get('onboarded'):
        return redirect(url_for('onboard'))
    analysis = db.get_analysis(uid)
    actions = db.get_actions(uid)
    return render_template('dashboard.html', user=user, analysis=analysis, actions=actions)


@app.route('/chat')
def chat():
    uid = get_user_id()
    user = db.get_or_create_user(uid)

    active = db.get_active_session(uid)
    if not active:
        sid = db.create_chat_session(uid, 'New Chat')
        active = {'id': sid, 'title': 'New Chat'}

    sessions = db.get_chat_sessions(uid)
    history = db.get_conversation(uid, session_id=active['id'], limit=50)

    return render_template('index.html',
        user=user,
        sessions=sessions,
        active_session=active,
        history=history
    )


@app.route('/profile')
def profile():
    uid = get_user_id()
    user = db.get_user(uid)
    if not user or not user.get('onboarded'):
        return redirect(url_for('onboard'))
    return render_template('profile.html', user=user)


# ─── API: Onboarding ─────────────────────────────────────────

@app.route('/api/onboard', methods=['POST'])
def api_onboard():
    uid = get_user_id()
    data = request.get_json()

    db.update_user(uid,
        resume_text=data.get('resume', ''),
        target_role=data.get('target_role', ''),
        timeline=data.get('timeline', ''),
        work_preference=data.get('work_preference', ''),
        interests=data.get('interests', ''),
        education=data.get('education', ''),
        onboarded=1
    )

    return jsonify({'status': 'ok'})


@app.route('/api/profile/update', methods=['POST'])
def api_profile_update():
    """Update individual profile fields without re-running full onboarding."""
    uid = get_user_id()
    data = request.get_json()

    allowed = {'target_role', 'timeline', 'work_preference', 'interests', 'education', 'resume_text'}
    updates = {k: v for k, v in data.items() if k in allowed}

    if updates:
        db.update_user(uid, **updates)

    return jsonify({'status': 'ok'})


@app.route('/api/upload-resume', methods=['POST'])
def api_upload_resume():
    uid = get_user_id()

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'No file selected'}), 400

    text = extract_text_from_file(f)
    if not text:
        return jsonify({'error': 'Could not extract text from this file. Try PDF, DOCX, or TXT.'}), 400

    db.update_user(uid, resume_text=text)
    return jsonify({'status': 'ok', 'text': text})


# ─── API: AI Career Analysis ─────────────────────────────────

@app.route('/api/analyze', methods=['GET', 'POST'])
def api_analyze():
    uid = get_user_id()
    user = db.get_user(uid)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    profile = build_profile_context(user)
    if not profile:
        return jsonify({'error': 'No profile data'}), 400

    analysis_prompt = f"""Analyze this person's career profile and return a JSON object (no markdown, just raw JSON).

{profile}

Return this exact JSON structure:
{{
  "summary": "2-3 sentence career profile summary",
  "current_skills": ["skill1", "skill2", ...],
  "career_paths": [
    {{
      "title": "Career Title",
      "match_score": 85,
      "timeline": "6-12 months",
      "salary_range": "$80k-$120k",
      "risk_level": "low|medium|high",
      "description": "Why this fits them",
      "key_steps": ["step1", "step2", "step3"]
    }}
  ],
  "skill_gaps": [
    {{
      "skill": "Skill Name",
      "importance": "critical|high|medium",
      "current_level": "none|beginner|intermediate",
      "action": "Specific way to build this skill"
    }}
  ],
  "weekly_actions": [
    {{
      "title": "Specific task title",
      "description": "What to do and why",
      "category": "learning|networking|portfolio|applications"
    }}
  ],
  "market_insight": "1-2 sentences about current market conditions relevant to their goals"
}}

Provide 3-5 career paths, 4-6 skill gaps, and 5-7 weekly actions.
Be extremely specific — reference their actual background, not generic advice.
Weekly actions should be completable in one week and directly advance their career transition."""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a career analysis engine. Return only valid JSON, no markdown fences."},
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=2000,
            temperature=0.7,
        )
        content = response.choices[0].message.content or ""
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        analysis = json.loads(content)
        db.save_analysis(uid, analysis)

        db.clear_actions(uid)
        if analysis.get('weekly_actions'):
            db.add_actions(uid, analysis['weekly_actions'], week=1)

        return jsonify({'status': 'ok', 'analysis': analysis})

    except json.JSONDecodeError:
        return jsonify({'error': 'Failed to parse AI analysis. Please try again.'}), 500
    except RateLimitError:
        return jsonify({'error': 'Rate limit exceeded. Please wait a moment.'}), 429
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── API: Chat (context-aware) ───────────────────────────────

@app.route('/api/chat', methods=['POST'])
def api_chat():
    uid = get_user_id()
    user = db.get_user(uid)
    user_input = request.form.get('msg', '').strip()
    session_id = request.form.get('session_id', type=int)
    if not user_input:
        return jsonify({'error': 'Empty message'}), 400

    active = db.get_active_session(uid)
    if not active:
        session_id = db.create_chat_session(uid, user_input[:50])
    else:
        session_id = active['id']

    db.save_message(uid, 'user', user_input, session_id=session_id)
    history = db.get_conversation(uid, session_id=session_id, limit=30)

    # Auto-title new sessions from first message
    sess_messages = db.get_conversation(uid, session_id=session_id, limit=2)
    if len(sess_messages) == 1:
        db.update_session_title(session_id, user_input[:60])

    profile_context = build_profile_context(user) if user else ""
    system_content = SYSTEM_PROMPT
    if profile_context:
        system_content += f"\n\n--- USER PROFILE ---\n{profile_context}"

    analysis = db.get_analysis(uid)
    if analysis and user:
        system_content += f"\n\n--- CAREER ANALYSIS ---\n"
        system_content += f"Summary: {analysis.get('summary', '')}\n"
        system_content += f"Target: {user.get('target_role', '')}\n"
        skills = analysis.get('current_skills', [])
        if skills:
            system_content += f"Current skills: {', '.join(skills[:10])}\n"
        gaps = analysis.get('skill_gaps', [])
        if gaps:
            system_content += f"Key gaps: {', '.join(g['skill'] for g in gaps[:5])}\n"

    messages = [{"role": "system", "content": system_content}]
    for msg in history:
        messages.append({"role": msg['role'], "content": msg['content']})

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,  # type: ignore[arg-type]
            max_tokens=1024,
        )
        content = response.choices[0].message.content
        reply = content.strip() if content else "No response received."
        db.save_message(uid, 'assistant', reply, session_id=session_id)
        return jsonify({'reply': reply, 'session_id': session_id})
    except RateLimitError:
        time.sleep(1)
        return jsonify({'error': 'Rate limit exceeded. Please try again in a moment.'}), 429
    except Exception as e:
        return jsonify({'error': f'Something went wrong: {str(e)}'}), 500


# ─── API: Chat Sessions ──────────────────────────────────────

@app.route('/api/sessions', methods=['GET'])
def api_sessions():
    uid = get_user_id()
    sessions = db.get_chat_sessions(uid)
    return jsonify({'sessions': sessions})


@app.route('/api/sessions/new', methods=['POST'])
def api_new_session():
    uid = get_user_id()
    sid = db.create_chat_session(uid, 'New Chat')
    db.set_active_session(uid, sid)
    return jsonify({'status': 'ok', 'session_id': sid})


@app.route('/api/sessions/switch', methods=['POST'])
def api_switch_session():
    uid = get_user_id()
    data = request.get_json()
    sid = data.get('session_id')
    if sid:
        db.set_active_session(uid, sid)
        history = db.get_conversation(uid, session_id=sid, limit=50)
        return jsonify({'status': 'ok', 'history': history})
    return jsonify({'error': 'No session_id'}), 400


@app.route('/api/sessions/delete', methods=['POST'])
def api_delete_session():
    uid = get_user_id()
    data = request.get_json()
    sid = data.get('session_id')
    if sid:
        db.delete_chat_session(sid, uid)
    return jsonify({'status': 'ok'})


# ─── API: Actions ─────────────────────────────────────────────

@app.route('/api/actions/toggle', methods=['POST'])
def api_toggle_action():
    uid = get_user_id()
    data = request.get_json()
    action_id = data.get('action_id')
    if action_id:
        db.toggle_action(action_id, uid)
    return jsonify({'status': 'ok'})


@app.route('/api/actions/refresh', methods=['POST'])
def api_refresh_actions():
    uid = get_user_id()
    user = db.get_user(uid)
    analysis = db.get_analysis(uid)
    if not user or not analysis:
        return jsonify({'error': 'No profile data'}), 400

    completed = [a for a in db.get_actions(uid) if a['completed']]
    completed_titles = [a['title'] for a in completed]

    profile = build_profile_context(user)
    prompt = f"""Based on this career profile and their completed tasks, generate 5-7 NEW weekly actions.

{profile}

Previously completed tasks: {', '.join(completed_titles) if completed_titles else 'None yet'}

Return only a JSON array:
[{{"title": "...", "description": "...", "category": "learning|networking|portfolio|applications"}}]

Make tasks specific, actionable, and progressive (building on completed work)."""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Return only valid JSON array, no markdown."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.7,
        )
        content = response.choices[0].message.content or ""
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        new_actions = json.loads(content)
        current_actions = db.get_actions(uid)
        max_week = max((a['week'] for a in current_actions), default=0)

        db.add_actions(uid, new_actions, week=max_week + 1)
        return jsonify({'status': 'ok', 'actions': new_actions, 'week': max_week + 1})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── API: Export & Reset ──────────────────────────────────────

@app.route('/api/export', methods=['GET'])
def api_export():
    uid = get_user_id()
    active = db.get_active_session(uid)
    sid = active['id'] if active else None
    history = db.get_conversation(uid, session_id=sid, limit=200)
    user = db.get_user(uid)

    lines = ["APTIGENIC — Career Operating System", "=" * 40, ""]
    if user and user.get('target_role'):
        lines.append(f"Target Role: {user['target_role']}")
        lines.append("")

    for msg in history:
        role = "You" if msg['role'] == 'user' else "Aptigenic"
        lines.append(f"{role}:\n{msg['content']}\n")

    return jsonify({'text': '\n'.join(lines)})


@app.route('/api/reset', methods=['POST'])
def api_reset():
    uid = get_user_id()
    db.clear_conversation(uid)
    db.clear_actions(uid)
    db.update_user(uid,
        resume_text='', target_role='', timeline='',
        work_preference='', interests='', education='',
        experience_summary='', analysis_json='', onboarded=0
    )
    return jsonify({'status': 'ok'})


if __name__ == "__main__":
    app.run(debug=True)
