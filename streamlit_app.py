import streamlit as st
import sqlite3
import hashlib
import datetime
import requests
import json
import time
import random
import textwrap
import os
from openai import OpenAI

#--- DataBase & Authentication Configuration ---
DB_PATH = "journal.db"
API_URL = "https://api.openai.com/v1/chat/completions"

#--- DataBase Functions ---
def init_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    #create users tablefor login and security
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
             id INTEGER PRIMARY KEY,
             username TEXT UNIQUE NOT NULL,
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

def register_user(username, password):
    """Registers a new user and returns their user ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        hashed_password = hash_password(password)
        cursor.execute("INSERT INTO users (username, password) Values (?, ?)", (username, hashed_password))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id, None
    except sqlite3.IntegrityError:
        conn.close()
        return None, "An account with this username already exists."

def login_user(username, password):
    """Logs in a user and returns their user ID if credentials are correct."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    hashed_password = hash_password(password)
    cursor.execute("SELECT id FROM users WHERE username=? AND password=?", (username, hashed_password))
    user = cursor.fetchone()
    conn.close()
    return user[0] if user else None

def get_username(user_id):
    """Fetches the username for a given user ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id=?", (user_id,))
    username = cursor.fetchone()
    conn.close()
    return username[0] if username else None

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
    cursor.execute("SELECT content, ai_response FROM entries WHERE user_id=? ORDER BY id  DESC LIMIT 1", (user_id, ))
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
    update_streak(user_id, date_str)
    conn.close()

def delete_entry(entry_id):
    """Deletes a journal entry by its ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM entries WHERE id =?", (entry_id,))
    conn.commit()
    conn.close()

def update_streak(user_id, current_date_str):
    """updates the user's journaling streak."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    current_date = datetime.date.fromisoformat(current_date_str)
    #check for existing streak
    cursor.execute("SELECT streak_count, last_entry_date FROM streaks WHERE user_id=?", (user_id,))
    streak_date = cursor.fetchone()
    if streak:
        streak_count, last_entry_date_str = streak_data
        if last_entry_date_str:
            last_entry_date = datetime.date.fromisofformat(last_entry_date_str)
            if (current_date - last_entry_date).days == 1:
                streak_count += 1
            elif (current_date - last_entry_date).days > 1:
                streak_count = 1
        else:
            streak_count = 1
        cursor.execute("UPDATE streaks SET streak_count=?, last_entry_date=? WHERE user_id=?", (streak_count, current_date_str, user_id))
    else:
        cursor.execute("INSERT into streaks (user_id, streak_count, last_entry_date) VALUES (?, 1, ?)", (user_id, current_date_str))
    conn.commit()
    conn.close()

def get_streak(user_id):
    """Fetches the user's current streak count."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT streak_count FROM streaks WHERE user_id=?", (user_id,))
    streak = cursor.fetchone()
    conn.close()
    return streak[0] if streak else 0

def get_total_entries(user_id):
    """Fetches the total number of journal entries for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM entries WHERE user_id=?", (user_id,))
    total = cursor.fetchone()
    conn.close()
    return total[0] if total else 0

def get_all_entries(user_id):
    """Fetches all journal entries for a user, ordered by date."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, content, mood, ai_response FROM entries WHEREuser_id=? ORDER BY date DESC", (user_id,))
    entries = cursor.fetchall()
    conn.close()
    return entries

def get_entry_dates(user_id):
    """Fetches the dates of all journal entries for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM entries WHERE user_id=? ORDER BY date ASC", (user_id,))
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return dates

openai.api_key = st.secrets["OPENAI_API_KEY"]  
#--- OpenAI API Functions ---
def generate_ai_response(entry_text):
    """
    Generates a creative, personalized AI response based on the journal entry.
    This function uses the OpenAI API. If the API fails, it provides a fallback message.
    """
    fallback_responses = [
        "Your thoughts are a garden, adn every entry is a seed. Keep nurturing them, and they will blossom into something beautiful.",
        "Remember that even the most beautiful stories have chapters of quiet moments. Your journey is uniquelyyours, and every page is worth writing.",
        "Take a deep breath and know that you are capable of incredible things. This moment is just a step on your path.",
        "Every day is a fresh start, a blank page waiting for your words. Embrace the new beginning."
    ]

    prompt = f"""
    You are MindScribe - an AI-powered journal assistant.
    your mission is to take the user's journal entry and transform it into something that sparks powerful emotions.
    Choose one of the following formats:
    - A Poem
    - A motivational quote
    - A short humorous dramatic story
    - A one-act play

    Guidelines:
    - The response must feel personal and directly inspired by the user's journal entry.
    - The tone can be motivational (fire-in-the-soul energy), humorous (laugh-out-loud funny), dramatic (mini stage-play), or uplifting (heartwarming).
    - Make it engaging, creative, and memorable - the kind of response that either makes the user laugh so hard that can't stop, or feel unstoppable motivation to conquer their goals.
    
    Here is the journal entry:
    \"\"\"{entry_text}\"\"\"

    Now, generate a creative response in ONE of the above formats that will either inspire, motivate or bring deep joy to the user.
    """
    prompt = textwrap.dedent(prompt)

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a creative, empathetic AI journal assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"AI Error: {e}")
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

def reset_session():
    """Resets the session state to log the user out."""
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.page = "login"
    st.rerun()


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
    .stSidebar {
        background-color: #90e8d7;
        color: white;
    }
    .centered-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        padding: 1em;
        border: 2px solid #2b2b29;
        border-radius: 10px;
        margin-bottom: 1em;
    }
    .popup-container {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background-color: #90e8d7;
        color: white;
        padding: 2em;
        border-radius: 15px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.5);
        z-index: 1000;
        text-align: center;
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
    st.write("Login or create a new account to begin your journey...")
    
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login", use_container_width = True):
            user_id = login_user(username, password)
            if user_id:
                st.session_state.user_id = user_id
                passcode = get_user_passcode(user_id)
                if passcode:
                    st.session_state.page = "security_check"
                else:
                    st.session_state.page = "welcome"
                st.rerun()
            else:
                st.error("Invalid username or password.")
    with col2:
        if st.button("Register", use_container_width = True):
            user_id, error = register_user(username, password)
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
        st.image(logo_image_path, width=150)
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

    username = get_username(st.session_state.user_id)
    slogans = [
        "Are you a work of art?? Because I'm mesmerized..🤩",
        "You're not just a Star🌟, you're the whole damn galaxy!! 🌌",
        "I was going to give you a compliment, but I'm gagged by your existence.. 🤩",
        "You must be a parking ticket, 'cause you've got fine written all over you.. 😉",
        "Are you a bank loan? Beacause you have my interest.. 🤌",
        "Are you an alien?? Because you just abducted my heart.. 💗",
        "Are you a search engine?? Because you're evrything I've been looking for.. 😁",
        "You must be a magician, because everytime i look at you, everyone else disappears.. 🙈",
        "You must be a good thief, because you are the only one who stole my heart on this globe.. 🫣"
    ]
    compliment = random.choice(slogans)
    
    st.markdown(
        f"""
        <div class = "welcome-container">
            <h1 class = "welcome-title"> Welcome, {username}!! 💖</h1>
            <p class = "welcome-subtitle"> {compliment}</p>
        </div>
        """,
        unsafe_allow_html = True
    )

    st.write(f"Your User ID is: AIMS **{st.session_state.user_id}**")
    st.button("Start Journaling", use_container_width = True, on_click = lambda: st.session_state.update(page="journal"))

def show_home_page():
    """Renders the new home page dashboard.."""
    logo_image_path = "MindScribe_logo.jpg"
    try:
        st.image(logo_image_path, width = 150)
    except FileNotFoundError:
        st.markdown('<div style= "color: #FFD700; font-size: 3em; font-weight: bold; text-align: center; margin-bottom: 1em; "> MindScribe </div>', unsafe_allow_html = True)
        st.warning(f"Logo file '{logo_image_path}' not found. Using fallback text.")
    st.title("Your Journal Dashboard..")
    st.write("A Quick Look At Your Progress...")
    #display key metrics
    current_streak = get_streak(st.session_state.user_id)
    total_entries = get_total_entries(st.session_state.user_id)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
            <div class = "centered-container">
                <h3> Current Streak </h3>
                <h2> <span style = "color: #FFD700;"> {current_streak} </span> days 🔥 </h2>
            </div>
            """,
            unsafe_allow_html = True
        )
    with col2:
        st.markdown(
            f"""
            <div class = "centered-container">
                <h3> Total Entries </h3>
                <h2> <span style = "color: #FFD700;"> {total_entries} </span> </h2>
            </div>
            """,
            unsafe_allow_html = True
        )
    st.markdown("---")
    #Calendar View
    st.subheader("Your Calendar")
    entry_dates = get_entry_dates (st.session_state.user_id)
    if entry_dates:
        st.write("Dates you've journaled:")
        st.write(",".join(entry_dates))
    else:
        st.info("Start writing to see your calendar history!!")
    st.markdown("---")
    #Previous entries list with delete option
    st.subheader("Previous Entries")
    entries = get_all_entries(st.session_state.user_id)
    if entries:
        for entry in entries:
            entry_id, date_str, content, mood, ai_response = entry
            with st.expander(f"**{date_sstr}** - Mood: {mood}"):
                st.write(f"**My thoughts:**")
                st.write(content)
                st.write("---")
                st.write(f"**Your AI Insight:**")
                st.write(ai_response)
                #delete button
                if st.button("delete this entry", key=f"delete_{entry_id}"):
                    delete_entry(entry_id)
                    st.success("Entry deleted successfully!! 🎉")
                    st.rerun()
    else:
        st.info("You don't have any past entries yet.. GoAhead journal one!!")
    st.markdown("---")
    #New Journaal Entry Button
    st.button("Write New Entry", use_container_width = True, on_click=lambda: st.session_state.update(page = "journal"))
    #LogOut button in the sidebar
    if st.sidebar.button("Log Out "):
        reset_session()


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
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Entry", use_container_width = True):
            if journal_entry:
                with st.spinner('Generating your personalized AI insight...'):
                    ai_response = generate_ai_response(journal_entry)
                save_entry(st.session_state.user_id, journal_entry, mood, ai_response)
                st.session_state.entry_saved = True
                st.session_state.ai_resonse = ai_response
                st.rerun()
            else:
                st.session_state.entry_saved = False
                st.warning("Please write something before saving..")
    with col2:
        if st.button("Back to Home", use_container_width = True):
            st.session_state.page = "home"
            st.rerun()
    if st.session_state.entry_saved:
        with st.container():
            st.markdown(
                """
                <div class = "popup-container">
                    <h3> Your AI Insight </h3>
                    <p style="font-style: italic;"> {response} </p>
                </div>
                """.format(response=st.session_state.ai_response),
                unsafe_allow_html  = True
            )
            st.session_state.entry_saved = False
    if st.sidebar.button("Log Out"):
        reset_session()
                

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
    elif st.session_state.page == "home":
        show_home_page()
    elif st.session_state.page == "journal":
        show_journal_page()
main_app()
