import streamlit as st
import json
import os
from datetime import datetime
import re
import hashlib
import base64
from io import BytesIO
import markdown
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import google.generativeai as genai

# Configure Streamlit page
st.set_page_config(
    page_title="DriftNotes",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- START: INITIAL APP PASSWORD PROTECTION ---
# Initialize session state variables for authentication
if "app_authenticated" not in st.session_state:
    st.session_state.app_authenticated = False
if "app_login_attempts" not in st.session_state:
    st.session_state.app_login_attempts = 0

# Define the maximum number of allowed attempts
MAX_APP_ATTEMPTS = 3

try:
    # The password should be set in your Streamlit secrets
    # e.g., in .streamlit/secrets.toml
    # driftnotes_app_password = "your_secret_password"
    correct_app_password = st.secrets["driftnotes_app_password"]
except KeyError:
    st.error("`driftnotes_app_password` not found in secrets.toml. Please set it to run the app.")
    st.stop()

# If not authenticated for initial app access, show the login screen.
if not st.session_state.app_authenticated:
    
    # Check if the user is locked out
    if st.session_state.app_login_attempts >= MAX_APP_ATTEMPTS:
        st.markdown('<div style="text-align: center; margin-top: 100px;">', unsafe_allow_html=True)
        st.error("🚫 **Access Blocked**")
        st.warning("Too many incorrect password attempts.Warning!")
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()

    # Display the login form
    st.markdown('<div style="text-align: center; margin-top: 100px;">', unsafe_allow_html=True)
    st.markdown("<h2 style='color: #9f7aea;'>DriftNotes Login</h2>", unsafe_allow_html=True)
    
    password_input = st.text_input(
        "Enter Password",
        type="password",
        key="app_password_input_field",
        label_visibility="collapsed",
        placeholder="Enter app password to unlock DriftNotes"
    )
    
    if st.button("Unlock App", use_container_width=True):
        if password_input == correct_app_password:
            st.session_state.app_authenticated = True
            st.session_state.app_login_attempts = 0 # Reset on success
            st.rerun()
        else:
            st.session_state.app_login_attempts += 1
            attempts_left = MAX_APP_ATTEMPTS - st.session_state.app_login_attempts
            st.error(f"Incorrect password. You have {attempts_left} attempt(s) left.")
            st.rerun() # Rerun to update the UI and check the lockout condition
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()
# --- END: INITIAL APP PASSWORD PROTECTION ---

# Database file
DB_FILE = "noirnotes_db.json"

# Initialize Gemini AI
def init_gemini():
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            return genai.GenerativeModel('gemma-3-27b-it')
        return None
    except:
        return None

def create_pdf(note):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        textColor=colors.black
    )
    story.append(Paragraph(note['title'], title_style))
    story.append(Spacer(1, 12))
    
    # Content
    content_style = ParagraphStyle(
        'CustomContent',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=12,
        textColor=colors.black
    )
    
    # Convert markdown to HTML then to PDF-compatible format
    html_content = markdown.markdown(note['content'])
    story.append(Paragraph(html_content, content_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# Initialize database
def init_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w') as f:
            json.dump({"notes": [], "settings": {"theme": "nebula", "locked": False, "ai_enabled": True}}, f)

def load_db():
    init_db()
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Themes
THEMES = {
    "nebula": {
        "primary": "#9f7aea",
        "secondary": "#ed64a6",
        "accent": "#4fd1c7",
        "bg": "#1a1a2e",
        "card_bg": "rgba(159, 122, 234, 0.1)"
    },
    "ocean": {
        "primary": "#4fd1c7",
        "secondary": "#38b2ac",
        "accent": "#63b3ed",
        "bg": "#0d1b2a",
        "card_bg": "rgba(79, 209, 199, 0.1)"
    },
    "forest": {
        "primary": "#48bb78",
        "secondary": "#38a169",
        "accent": "#ecc94b",
        "bg": "#1a202c",
        "card_bg": "rgba(72, 187, 120, 0.1)"
    },
    "classic": {
        "primary": "#e2e8f0",
        "secondary": "#cbd5e0",
        "accent": "#a0aec0",
        "bg": "#0f0f0f",
        "card_bg": "rgba(226, 232, 240, 0.05)"
    }
}

# Apply CSS styling
def apply_theme(theme_name):
    theme = THEMES[theme_name]
    st.markdown(f"""
    <style>
    .stApp {{
        background: {theme['bg']};
        color: {theme['primary']};
        font-family: 'JetBrains Mono', monospace;
    }}
    
    .main-header {{
        text-align: center;
        color: {theme['primary']};
        text-shadow: 0 0 10px {theme['secondary']};
        margin-bottom: 2rem;
        font-size: 2.5rem;
        font-weight: 700;
    }}
    
    .note-card {{
        background: {theme['card_bg']};
        backdrop-filter: blur(10px);
        border: 1px solid {theme['primary']}33;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
    }}
    
    .note-card:hover {{
        border-color: {theme['secondary']};
        box-shadow: 0 0 20px {theme['secondary']}33;
        transform: translateY(-2px);
    }}
    
    .note-title {{
        color: {theme['secondary']};
        font-size: 1.4rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        text-shadow: 0 0 5px {theme['secondary']};
    }}
    
    .note-preview {{
        color: {theme['primary']};
        opacity: 0.8;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }}
    
    .note-meta {{
        color: {theme['accent']};
        font-size: 0.8rem;
        opacity: 0.7;
    }}
    
    .tag {{
        background: {theme['secondary']}22;
        color: {theme['secondary']};
        padding: 0.2rem 0.6rem;
        border-radius: 20px;
        font-size: 0.7rem;
        margin: 0.2rem;
        border: 1px solid {theme['secondary']}44;
        display: inline-block;
    }}
    
    .pinned {{
        border-color: {theme['accent']} !important;
        box-shadow: 0 0 15px {theme['accent']}44;
    }}
    
    .stats {{
        background: {theme['card_bg']};
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        border: 1px solid {theme['primary']}22;
    }}
    
    .sidebar .stSelectbox > div > div {{
        background: {theme['card_bg']};
        border: 1px solid {theme['primary']}44;
    }}
    
    .stTextInput > div > div > input {{
        background: {theme['card_bg']};
        border: 1px solid {theme['primary']}44;
        color: {theme['primary']};
    }}
    
    .stTextArea > div > div > textarea {{
        background: {theme['card_bg']};
        border: 1px solid {theme['primary']}44;
        color: {theme['primary']};
        font-family: 'JetBrains Mono', monospace;
    }}
    
    .stButton > button {{
        background: {theme['secondary']};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }}
    
    .ai-suggestion {{
        background: linear-gradient(135deg, {theme['secondary']}22, {theme['accent']}22);
        border: 1px solid {theme['accent']}44;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        position: relative;
    }}
    
    .ai-suggestion::before {{
        content: "✨";
        position: absolute;
        top: -5px;
        right: -5px;
        background: {theme['accent']};
        border-radius: 50%;
        width: 20px;
        height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 10px;
    }}
    
    .ai-button {{
        background: linear-gradient(135deg, {theme['accent']}, {theme['secondary']});
        border: none;
        border-radius: 20px;
        padding: 0.3rem 0.8rem;
        color: white;
        font-size: 0.8rem;
        cursor: pointer;
        transition: all 0.3s ease;
    }}
    
    .ai-button:hover {{
        transform: scale(1.05);
        box-shadow: 0 0 15px {theme['accent']}66;
    }}
    
    .ai-loading {{
        color: {theme['accent']};
        animation: pulse 1.5s infinite;
    }}
    
    @keyframes pulse {{
        0%, 100% {{ opacity: 0.5; }}
        50% {{ opacity: 1; }}
    }}
    </style>
    """, unsafe_allow_html=True)

# Utility functions
def generate_id():
    return hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]

def word_count(text):
    return len(re.findall(r'\w+', text))

def reading_time(text):
    words = word_count(text)
    return max(1, round(words / 200))  # 200 WPM average

def extract_tags(content):
    return re.findall(r'#(\w+)', content)

def filter_notes(notes, search_term="", tag_filter=""):
    if not search_term and not tag_filter:
        return notes
    
    filtered = []
    for note in notes:
        search_match = not search_term or (
            search_term.lower() in note['title'].lower() or 
            search_term.lower() in note['content'].lower()
        )
        tag_match = not tag_filter or tag_filter in note.get('tags', [])
        
        if search_match and tag_match:
            filtered.append(note)
    
    return filtered

# Gemini AI functions
def generate_ai_suggestions(model, note_content, suggestion_type="improve"):
    if not model:
        return None
    
    prompts = {
        "improve": f"Analyze this note and suggest 3 ways to improve it:\n\n{note_content}",
        "summarize": f"Create a concise summary of this note:\n\n{note_content}",
        "tags": f"Suggest 5 relevant hashtags for this note:\n\n{note_content}",
        "continue": f"Continue writing this note with 2-3 more sentences:\n\n{note_content}",
        "title": f"Suggest 3 creative titles for this note:\n\n{note_content}"
    }
    
    try:
        response = model.generate_content(prompts[suggestion_type])
        return response.text
    except Exception as e:
        return f"AI unavailable: {str(e)}"

def get_smart_insights(model, notes):
    if not model or not notes:
        return None
    
    recent_notes = notes[-5:]  # Last 5 notes
    content_sample = "\n".join([f"- {note['title']}: {note['content'][:100]}..." for note in recent_notes])
    
    prompt = f"""Analyze these recent notes and provide insights:
    {content_sample}
    
    Provide:
    1. Main themes/topics
    2. Writing patterns
    3. Productivity suggestions"""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return None
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        textColor=colors.black
    )
    story.append(Paragraph(note['title'], title_style))
    story.append(Spacer(1, 12))
    
    # Content
    content_style = ParagraphStyle(
        'CustomContent',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=12,
        textColor=colors.black
    )
    
    # Convert markdown to HTML then to PDF-compatible format
    html_content = markdown.markdown(note['content'])
    story.append(Paragraph(html_content, content_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# Initialize session state
if 'current_note' not in st.session_state:
    st.session_state.current_note = None
if 'view' not in st.session_state:
    st.session_state.view = 'dashboard'
if 'auth' not in st.session_state:
    st.session_state.auth = False
if 'ai_suggestions' not in st.session_state:
    st.session_state.ai_suggestions = {}
if 'show_ai_panel' not in st.session_state:
    st.session_state.show_ai_panel = False

# Load data and initialize Gemini
db = load_db()
notes = db.get('notes', [])
settings = db.get('settings', {"theme": "nebula", "locked": False, "ai_enabled": True})
gemini_model = init_gemini() if settings.get('ai_enabled', True) else None

# Apply theme
apply_theme(settings['theme'])

# Authentication check
if settings.get('locked', False) and not st.session_state.auth:
    st.markdown('<div class="main-header">🔒 DriftNotes Vault</div>', unsafe_allow_html=True)
    
    password = st.text_input("Enter vault password:", type="password")
    if st.button("Unlock"):
        # Simple password check (in real app, use proper hashing)
        if password == settings.get('vault_password', 'drift123'):
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Invalid password!")
    st.stop()

# Header
st.markdown('<div class="main-header">🌌 DriftNotes</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### Navigation")
    
    if st.button("📊 Dashboard", use_container_width=True):
        st.session_state.view = 'dashboard'
        st.session_state.current_note = None
    
    if st.button("➕ New Note", use_container_width=True):
        st.session_state.view = 'edit'
        st.session_state.current_note = None
    
    st.markdown("---")
    
    # AI Settings
    if gemini_model:
        st.markdown("### 🎓 AI Assistant")
        ai_enabled = st.checkbox("Enable AI Features", value=settings.get('ai_enabled', True))
        
        if ai_enabled != settings.get('ai_enabled', True):
            settings['ai_enabled'] = ai_enabled
            db['settings'] = settings
            save_db(db)
            st.rerun()
        
        if ai_enabled and st.button("🧠 Smart Insights"):
            st.session_state.show_ai_panel = not st.session_state.show_ai_panel
    
    st.markdown("---")
    
    # Theme selector
    st.markdown("### 🎨 Theme")
    theme_options = {
        "nebula": "🌌 Nebula",
        "ocean": "🌊 Ocean", 
        "forest": "🌲 Forest",
        "classic": "🖤 Classic Noir"
    }
    
    current_theme = st.selectbox(
        "Choose theme:",
        options=list(theme_options.keys()),
        format_func=lambda x: theme_options[x],
        index=list(theme_options.keys()).index(settings['theme'])
    )
    
    if current_theme != settings['theme']:
        settings['theme'] = current_theme
        db['settings'] = settings
        save_db(db)
        st.rerun()
    
    st.markdown("---")
    
    # Search and filter
    st.markdown("### 🔍 Search & Filter")
    search_term = st.text_input("Search notes:")
    
    all_tags = set()
    for note in notes:
        all_tags.update(note.get('tags', []))
    
    tag_filter = st.selectbox("Filter by tag:", [""] + sorted(list(all_tags)))
    
    st.markdown("---")
    
    # Quote of the day
    quotes = [
        "Write what should not be forgotten. - Isabel Allende",
        "The secret to getting ahead is getting started. - Mark Twain",
        "Ideas are like rabbits. You get a couple and learn how to handle them, and pretty soon you have a dozen. - John Steinbeck",
        "Writing is thinking on paper. - William Zinsser",
        "In the dark, all thoughts glow. - DriftNotes"
    ]
    
    import random
    quote = quotes[datetime.now().day % len(quotes)]
    st.markdown(f"### 🌙 Daily Inspiration")
    st.markdown(f"*{quote}*")

# Main content area
if st.session_state.view == 'dashboard':
    # Dashboard view
    st.markdown("### 📝 Your Notes")
    
    # Stats
    total_notes = len(notes)
    total_words = sum(word_count(note['content']) for note in notes)
    pinned_count = len([n for n in notes if n.get('pinned', False)])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="stats">📚 <strong>{total_notes}</strong> notes</div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stats">📝 <strong>{total_words}</strong> words</div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stats">📌 <strong>{pinned_count}</strong> pinned</div>', unsafe_allow_html=True)
    
    # Smart Insights Panel
    if st.session_state.show_ai_panel and gemini_model and settings.get('ai_enabled'):
        with st.expander("🧠 AI Insights", expanded=True):
            insights = get_smart_insights(gemini_model, notes)
            if insights:
                st.markdown(f'<div class="ai-suggestion">{insights}</div>', unsafe_allow_html=True)
            else:
                st.info("Write more notes to get AI insights!")
    
    # Filter notes
    filtered_notes = filter_notes(notes, search_term, tag_filter)
    
    # Sort: pinned first, then by last updated
    filtered_notes.sort(key=lambda x: (not x.get('pinned', False), x.get('last_updated', '')), reverse=True)
    
    if not filtered_notes:
        st.info("No notes found. Create your first note!")
    
    # Display notes
    for note in filtered_notes:
        card_class = "note-card pinned" if note.get('pinned', False) else "note-card"
        
        with st.container():
            st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns([6, 1, 1])
            
            with col1:
                st.markdown(f'<div class="note-title">{note["title"]}</div>', unsafe_allow_html=True)
                
                # Preview
                preview = note['content'][:150] + "..." if len(note['content']) > 150 else note['content']
                st.markdown(f'<div class="note-preview">{preview}</div>', unsafe_allow_html=True)
                
                # Tags
                if note.get('tags'):
                    tags_html = ''.join([f'<span class="tag">#{tag}</span>' for tag in note['tags']])
                    st.markdown(tags_html, unsafe_allow_html=True)
                
                # Meta info
                words = word_count(note['content'])
                read_time = reading_time(note['content'])
                updated = note.get('last_updated', note['timestamp'])[:16]
                
                st.markdown(f'<div class="note-meta">📝 {words} words • ⏱️ {read_time} min read • 📅 {updated}</div>', 
                          unsafe_allow_html=True)
            
            with col2:
                if st.button("✏️", key=f"edit_{note['id']}", help="Edit note"):
                    st.session_state.current_note = note
                    st.session_state.view = 'edit'
                    st.rerun()
            
            with col3:
                if st.button("🗑️", key=f"delete_{note['id']}", help="Delete note"):
                    notes.remove(note)
                    db['notes'] = notes
                    save_db(db)
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.view == 'edit':
    # Edit view
    is_new = st.session_state.current_note is None
    note = st.session_state.current_note or {
        'id': generate_id(),
        'title': '',
        'content': '',
        'tags': [],
        'timestamp': datetime.now().isoformat(),
        'pinned': False
    }
    
    st.markdown(f"### {'📝 New Note' if is_new else '✏️ Edit Note'}")
    
    # Title
    title = st.text_input("Title:", value=note['title'])
    
    # Content with live preview and AI assistance
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("**Editor**")
        content = st.text_area("Content (Markdown supported):", 
                              value=note['content'], 
                              height=400,
                              help="Use # for headers, **bold**, *italic*, `code`, etc.")
        
        # AI assistance buttons
        if gemini_model and settings.get('ai_enabled') and content:
            st.markdown("**🎓 AI Assistant**")
            col_ai1, col_ai2, col_ai3 = st.columns(3)
            
            with col_ai1:
                if st.button("✨ Improve", key="ai_improve", help="Get improvement suggestions"):
                    with st.spinner("AI thinking..."):
                        suggestion = generate_ai_suggestions(gemini_model, content, "improve")
                        st.session_state.ai_suggestions['improve'] = suggestion
            
            with col_ai2:
                if st.button("📝 Continue", key="ai_continue", help="Continue writing"):
                    with st.spinner("AI writing..."):
                        suggestion = generate_ai_suggestions(gemini_model, content, "continue")
                        st.session_state.ai_suggestions['continue'] = suggestion
            
            with col_ai3:
                if st.button("🏷️ Tags", key="ai_tags", help="Suggest tags"):
                    with st.spinner("AI tagging..."):
                        suggestion = generate_ai_suggestions(gemini_model, content, "tags")
                        st.session_state.ai_suggestions['tags'] = suggestion
            
            # Display AI suggestions
            for sug_type, sug_content in st.session_state.ai_suggestions.items():
                if sug_content:
                    with st.expander(f"✨ {sug_type.title()} Suggestions"):
                        st.markdown(f'<div class="ai-suggestion">{sug_content}</div>', unsafe_allow_html=True)
                        if st.button(f"Clear {sug_type}", key=f"clear_{sug_type}"):
                            del st.session_state.ai_suggestions[sug_type]
                            st.rerun()
    
    with col2:
        st.markdown("**Preview**")
        if content:
            try:
                html_content = markdown.markdown(content, extensions=['codehilite', 'fenced_code'])
                st.markdown(html_content, unsafe_allow_html=True)
            except:
                st.markdown(content)
        else:
            st.info("Preview will appear here...")
        
        # AI Summary
        if gemini_model and settings.get('ai_enabled') and content and len(content) > 100:
            if st.button("📋 AI Summary", key="ai_summary"):
                with st.spinner("Summarizing..."):
                    summary = generate_ai_suggestions(gemini_model, content, "summarize")
                    st.markdown("**Quick Summary:**")
                    st.markdown(f'<div class="ai-suggestion">{summary}</div>', unsafe_allow_html=True)
    
    # Options
    col1, col2, col3 = st.columns(3)
    with col1:
        pinned = st.checkbox("📌 Pin note", value=note.get('pinned', False))
    with col2:
        if content:
            st.info(f"📝 {word_count(content)} words")
    with col3:
        if content:
            st.info(f"⏱️ {reading_time(content)} min read")
    
    # Auto-extract tags and AI suggestions
    extracted_tags = extract_tags(content)
    
    # AI title suggestions
    if gemini_model and settings.get('ai_enabled') and content and not title:
        if st.button("🎯 AI Title Ideas", key="ai_title"):
            with st.spinner("Generating titles..."):
                title_suggestions = generate_ai_suggestions(gemini_model, content, "title")
                st.markdown("**Suggested Titles:**")
                st.markdown(f'<div class="ai-suggestion">{title_suggestions}</div>', unsafe_allow_html=True)
    
    if extracted_tags:
        st.info(f"Tags found: {', '.join([f'#{tag}' for tag in extracted_tags])}")
    
    # Action buttons
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("💾 Save", use_container_width=True):
            if title and content:
                note['title'] = title
                note['content'] = content
                note['tags'] = extracted_tags
                note['pinned'] = pinned
                note['last_updated'] = datetime.now().isoformat()
                
                if is_new:
                    notes.append(note)
                else:
                    # Update existing note
                    for i, existing_note in enumerate(notes):
                        if existing_note['id'] == note['id']:
                            notes[i] = note
                            break
                
                db['notes'] = notes
                save_db(db)
                
                st.success("Note saved!")
                st.session_state.view = 'dashboard'
                st.session_state.current_note = None
                st.rerun()
            else:
                st.error("Please provide both title and content")
    
    with col2:
        if st.button("🏠 Dashboard", use_container_width=True):
            st.session_state.view = 'dashboard'
            st.session_state.current_note = None
            st.rerun()
    
    with col3:
        if not is_new:
            if st.button("📄 Export MD", use_container_width=True):
                md_content = f"# {title}\n\n{content}"
                st.download_button(
                    label="Download Markdown",
                    data=md_content,
                    file_name=f"{title.replace(' ', '_')}.md",
                    mime="text/markdown"
                )
    
    with col4:
        if not is_new:
            if st.button("📑 Export PDF", use_container_width=True):
                try:
                    pdf_buffer = create_pdf({'title': title, 'content': content})
                    st.download_button(
                        label="Download PDF",
                        data=pdf_buffer,
                        file_name=f"{title.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"PDF export failed: {str(e)}")

# Settings in sidebar
with st.sidebar:
    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    
    # Vault lock
    if st.button("🔒 Toggle Vault Lock"):
        if settings.get('locked', False):
            settings['locked'] = False
            st.success("Vault unlocked!")
        else:
            password = st.text_input("Set vault password:", type="password", key="set_pass")
            if password and st.button("Set Password"):
                settings['locked'] = True
                settings['vault_password'] = password
                st.success("Vault locked!")
        
        db['settings'] = settings
        save_db(db)
    
    # Import/Export
    st.markdown("### 📥 Import/Export")
    
    # Export all notes
    if st.button("📤 Export All Notes"):
        export_data = {
            "notes": notes,
            "exported_at": datetime.now().isoformat(),
            "total_notes": len(notes)
        }
        
        st.download_button(
            label="Download JSON",
            data=json.dumps(export_data, indent=2),
            file_name=f"noirnotes_export_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )
    
    # Import notes
    uploaded_file = st.file_uploader("📂 Import Notes", type=['json'])
    if uploaded_file:
        try:
            import_data = json.load(uploaded_file)
            imported_notes = import_data.get('notes', [])
            
            # Add unique IDs to avoid conflicts
            for note in imported_notes:
                note['id'] = generate_id()
                note['imported_at'] = datetime.now().isoformat()
            
            notes.extend(imported_notes)
            db['notes'] = notes
            save_db(db)
            
            st.success(f"Imported {len(imported_notes)} notes!")
            st.rerun()
        except Exception as e:
            st.error(f"Import failed: {str(e)}")

    st.markdown("---")
    
    # AI Status
    if gemini_model:
        st.success("🎓 AI Assistant: Active")
    else:
        st.warning("🎓 AI Assistant: Unavailable")
        st.caption("Add GEMINI_API_KEY to Streamlit secrets")
    
    st.markdown("---")
    st.markdown("*DriftNotes v2.0 with AI 🌌*")
