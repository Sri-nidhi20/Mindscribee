import streamlit as st
import sqlite3
import hashlib
import datetime
import requests
import json
import time
import random
import textwrap

#--- DataBase & Authentication Configuration ---
DB_PATH = "journal.db"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"

#--- DataBase Functions ---
def init_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    #create users tablefor login and security
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
             id INTEGER PRIMARY KEY,
             email TEXT UNIQUE NOT NULL,
             password TEXT NOT NULL,
             passcode TEXT
        );
    """)
    #create journal entries table (to be used later)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            content TEXT NOT NULL,
            mood TEXT,
            ai_response TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    #create streaks table to track streaks (to be used later)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS streaks (
            user_id INTEGER PRIMARY KEY,
            streak_count INTEGER DEFAULT 0,
            last_entry_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()

def hash_password(password):
    """Hashes a password using SHA-256 for secure storage."""
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(email, password):
    """Registers a new user and returns their user ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        hashed_password = hash_password(password)
        cursor.execute("INSERT INTO users (email, password) Values (?, ?)", (email, hashed_password))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id, None
    except sqlite3.IntegrityError:
        conn.close()
        return None, "An account with this email already exists."

def login_user(email, password):
    """Logs in a user and returns their user ID if credentials are correct."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    hashed_password = hash_password(password)
    cursor.execute("SELECT id FROM users WHERE email=? AND password=?", (email, hashed_password))
    user = cursor.fetchone()
    conn.close()
    return user[0] if user else None

def set_security_key(user_id, passcode):
    """Sets a security passcode for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET passcode = ? WHERE id = ?", (passcode, user_id))
    conn.commit()
    conn.close()

def get_user_passcode(user_id):
    """Retrieves the security passcode for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT passcode FROM users WHERE id = ?", (user_id,))
    passcode = cursor.fetchone()
    conn.close()
    return passcode[0] if passcode else None

def get_last_entry_and_ai_response(user_id):
    """Fetches the last journal entry and its AI response for a given user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT content, ai_response FROM entries WHERE eser_id=? ORDER BY id  DESC LIMIT 1", (user_id, ))
    entry = cursor.fetchone()
    conn.close()
    return entry

def save_entry(user_id, content, mood, ai_response):
    """saves a new journal entry amd the AI response for the current user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    date_str = datetime.date.today().isoformat()
    cursor.execute("INSERT INTO entries (user_id, date, content, mood, ai_response) VALUES (?, ?, ?, ?, ?)", (user_id, date_str, content, mood, ai_response))
    conn.commit()
    conn.close()
    
#--- Gemini API Functions ---
def generate_ai_response(entry_text):
    """
    Generates a creative, personalized AI response based on the journal entry.
    This function uses the Gemini API. If the API fails, it provides a fallback message.
    """
    fallback_responses = [
        "Your thoughts are a garden, adn every entry is a seed. Keep nurturing them, and they will blossom into something beautiful.",
        "Remember that even the most beautiful stories have chapters of quiet moments. Your journey is uniquelyyours, and every page is worth writing.",
        "Take a deep breath and know that you are capable of incredible things. This moment is just a step on your path.",
        "Every day is a fresh start, a blank page waiting for your words. Embrace the new beginning."
    ]

    prompt = f"""
    You are an AI-powered journal assistant. Your task is to provide a creative and uplifting response to a user's journal entry. The response should be a poem, a short cringe humorous dramatic story, a motivational quote, or a short one-act play. The tone should be based on the content of the journal entry. Ensure the response is personalized and directly relates to the user's thoughts.

    Here is the journal entry:
    \"\"\"{entry_text}\"\"\"

    Choose a creative format and provide a response that aims to uplift, inspire or offer a new perspective.
    """
    prompt = textwrap.dedent(prompt)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 200,
        },
    }

    headers = {
        "Content-Type": "application/json",
    }

    api_key = "" #This will be provided by the environmenr

    retries = 0
    max_retries = 3
    while retries < max_retries:
        try:
            response = requests.post(f"{API_URL}?key={api_key}", headers=headers, data = json.dumps(payload))
            response.raise_for_status()
            response_json = response.json()
            #extract the AI's generated text
            if response_json and 'candidates' in response_json and len(response_json['candidates']) > 0:
                ai_text = response_json['candidates'][0]['content']['parts'][0]['text']
                return ai_text
            else:
                return random.choice(fallback_responses)
        except requests.exceptions.HTTPError as errh:
            st.error(f"HTTP Error: {errh}")
            break
        except requests.exceptions.ConnectionError as errc:
            st.error(f"Error Connecting: {errc}")
            break
        except requests.exceptions.Timeout as errt:
            st.error(f"Timeout Error: {errt}")
            break
        except requests.exceptions.RequestException as err:
            st.error(f"An unexpected error occurred: {err}")
            break
        except Exception as e:
            st.error(f"An Error occurred: {e}")
            break
        retries += 1
        time.sleep(2 ** retries) #exponential backoff
    return random.choice(fallback_responses)

#---Streamlit APP UI & Logic ---
        
#Initialize the database and session state
init_db()
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.page = "login"
    st.session_state.security_checked = False
    st.session_state.error_message = ""
    st.session_state.is_registering = False
    st.session_state.entry_saved = False 

#Custom CSS for background, text color, and logo
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0b5844;
        color: white;
    }
    .welcome-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        padding: 2em;
    }
    .welcome-title {
        font-size: 2.5em;
        font-weight: bold;
        margin-bottom: 1em;
    }
    .welcome-subtitle {
        font-size: 1.2em;
        margin-bottom: 1em;
    }
    .stButton > button {
        background-color: #FFD700;
        color: #0b5844;
        font-weight: bold;
        border-radius: 10px;
        border: none;
        padding: 10px 20px;
    }
    </style>
    """,
    unsafe_allow_html=True
)
    

def show_login_page():
    """Renders the login and registration UI."""
    logo_image_path = "MindScribe_logo.jpg"
    try:
        st.image(logo_image_path, width=150)
    except FileNotFoundError:
        st.markdown('<div style="color: #FFD700; font-size: 3em; font-weight: bold; text-align: center; margin-bottom: 1em;"> MindScribe </div>', unsafe_allow_html=True)
        st.warning(f"Logo file '{logo_image_path}' not found. using fallback text.")
        
    st.title("Welcome to MindScribe")
    st.subheader("Your AI-Powered Journal")
    st.write("Login or create a new account to begin.")
    
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login", use_container_width = True):
            user_id = login_user(email, password)
            if user_id:
                st.session_state.user_id = user_id
                passcode = get_user_passcode(user_id)
                if passcode:
                    st.session_state.page = "security_check"
                else:
                    st.session_state.page = "welcome"
                st.rerun()
            else:
                st.error("Invalid email or password.")
    with col2:
        if st.button("Register", use_container_width = True):
            user_id, error = register_user(email, password)
            if user_id:
                st.success("Account created! Please set a security key.")
                st.session_state.user_id = user_id
                st.session_state.page = "set_security_key"
                st.rerun()
            else:
                st.error(error)

def show_set_security_key_page():
    """Renders the security key setup UI."""
    logo_image_path = "MindScribe_logo.jpg"
    try:
        st.image(logo_iamge_path, width=150)
    except FileNotFoundError:
        st.markdown('<div style="color: #FFD700; font-size: 3em; font-weight: bold; text-align: center: margin-bottom: 1em;"> MindScribe </div>', unsafe_allow_html=True)
        st.warning(f"Logo file '{logo_image_path}' not found. Using fallback text.")
        
    st.title("Set a Security Key")
    st.write("Optional: Add a 4-digit key to project your journal entries.")
    
    passcode = st.text_input("Choose a 4-digit key", type="password", key="set_passcode")
    
    if st.button("Set Key"):
        if passcode and len(passcode) == 4 and passcode.isdigit():
            set_security_key(st.session_state.user_id, passcode)
            st.session_state.page = "welcome"
            st.success("Security key set successfully!")
            st.rerun()
        else:
            st.error("Please enter a 4-digit numeric key.")
    
    if st.button("Skip for now"):
        st.session_state.page = "welcome"
        st.rerun()

def show_security_check_page():
    """Renders the security key check UI."""
    logo_image_path = "MindScribe_logo.jpg"
    try:
        st.image(logo_image_path, width=150)
    except FileNotFoundError:
        st.markdown('<div style="color: #FFD700; font-size: 3em; font-weight: bold; text-align: center; margin-bottom: 1em;">MindScribe</div>', unsafe_allow_html=True)
        st.warning(f"Logo file '{logo_image_path}' not found. Using fallback text.")

    st.title("Enter your Security Key")
    st.write("Please enter your personal key to unlock you journal.")
    
    passcode_check = st.text_input("Enter your key", type="password", key = "check_passcode")
    
    if st.button("Unlock"):
        stored_passcode = get_user_passcode(st.session_state.user_id)
        if passcode_check == stored_passcode:
            st.session_state.page = "welcome"
            st.session_state.security_checked = True
            st.rerun()
        else:
            st.error("Incorrect security key. Please try again.")

def show_welcome_page():
    """A simple welcome page to show after successful login."""
    logo_image_path = "MindScribe_logo.jpg"
    try:
        st.image(logo_image_path, width=150)
    except FileNotFoundError:
        st.markdown('<div style="color: #FFD700; font-size: 3em; font-weight: bold; text-align: center; margin-bottom: 1em;">MindScribe</div>', unsafe_allow_html=True)
        st.warning(f"Logo file '{logo_image_path}' not found. Using fallback text.")
    
    st.markdown(
        """
        <div class = "welcome-container">
            <h1 class = "welcome-title"> Welcome to MindScribe</h1>
            <p class = "welcome-subtitle"> Your new ultimate AI-powered journal. </p>
        </div>
        """,
        unsafe_allow_html = True
    )

    st.write(f"Your User ID is: **{st.session_state.user_id}**")
    st.button("Start Journaling", use_container_width = True, on_click = lambda: st.session_state.update(page="journal"))

def show_journal_page():
    """Renders the main journaling page with AI sidebar."""
    logo_image_path = "MindScribe_logo.jpg"
    try:
        st.image(logo_image_path, width=150)
    except FileNotFoundError:
        st.markdown('<div style="color: #FFD700; font-size: 3em; font-weight: bold; text-align: center; margin-bottom: 1em;">MindScribe</div>', unsafe_allow_html=True)
        st.warning(f"Logo file '{logo_image_path}' not found. Using fallback text.")
    st.title("Journal Entry")
    st.write("Write about your day and we'll help you reflect on it.")
    journal_entry = st.text_area("What's on your mind today?", height=300)
    mood = st.selectbox("How are you feeling ?", ["Happy", "Sad", "Anxious", "Neutral", "Excited"])
    if st.button("Save Entry", use_container_width = True):
        if journal_entry:
            with st.spinner('Generating your personalized AI insight.....'):
                ai_response = generate_ai_response(journal_entry)
            save_entry(st.session_state.user_id, journal_entry, mood, ai_response)
            st.session_state.entry_saved = True
            st.success("Entry Saved!!")
            st.rerun()
        else:
            st.session_state.entry_saved = False
            st.warning("Please write something before saving.")
    #Display the AI sidebar if an was just saved
    if st.session_state.entry_saved:
        last_entry = get_last_entry_and_ai_response(st.session_state.user_id)
        if last_entry and last_entry[1]:
            with st.sidebar:
                st.markdown('<div style ="color: #FFd700; font-size: 1.5em; text-align: center;"> Your AI Insight </div>', unsafe_allow_html = True)
                st.markdown(f'<div style = "text-align: center; font-style: italic;"> {last_entry[1]}</div>', unsafe_allow_html = True)
                st.markdown("---")
                st.markdown('<div style = "text-align: center; color: white; font-weight: bold;"> Enjoy your journey!!</div>', unsafe_allow_html=True)
                

def main_app():
    """Handles page routing based on session state."""
    if st.session_state.page == "login":
        show_login_page()
    elif st.session_state.page == "set_security_key":
        show_set_security_key_page()
    elif st.session_state.page == "security_check":
        show_security_check_page()
    elif st.session_state["page"] == "welcome":
        show_welcome_page()
    elif st.session_state.page == "journal":
        show_journal_page()
main_app()
