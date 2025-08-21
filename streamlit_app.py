import streamlit as st
import sqlite3
import hashlib

#--- DataBase & Authentication Configuration ---
DB_PATH = "journal.db"

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

def show_login_page():
    """Renders the login and registration UI."""
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
                st.experimental_rerun()
            else:
                st.error("Invalid email or password.")
    with col2:
        if st.button("Register", use_container_width = True):
            user_id, error = register_user(email, password)
            if user_id:
                st.success("Account created! Please set a security key.")
                st.session_state.user_id = user_id
                st.session_state.page = "set_security_key"
                st.experimental_rerun()
            else:
                st.error(error)

def show_set_security_key_page():
    """Renders the security key setup UI."""
    st.title("Set a Security Key")
    st.write("Optional: Add a 4-digit key to project your journal entries.")
    
    passcode = st.text_input("Choose a 4-digit key", type="password", key="set_passcode")
    
    if st.button("Set Key"):
        if passcode and len(passcode) == 4 and passcode.isdigit():
            set_security_key(st.session_state.user_id, passcode)
            st.session_state.page = "welcome"
            st.success("Security key set successfully!")
            st.experimental_rerun()
        else:
            st.error("Please enter a 4-digit numeric key.")
    
    if st.button("Skip for now"):
        st.session_state.page = "welcome"
        st.experimental_rerun()

def show_security_check_page():
    """Renders the security key check UI."""
    st.title("Enter your Security Key")
    st.write("Please enter your personal key to unlock you journal.")
    
    passcode_check = st.text_input("Enter your key", type="password", key = "check_passcode")
    
    if st.button("Unlock"):
        stored_passcode = get_user_passcode(st.session_state.user_id)
        if passcode_check == stored_passcode:
            st.session_state.page = "welcome"
            st.session_state.security_checked = True
            st.experimental_rerun()
        else:
            st.error("Incorrect security key. Please try again.")

def show_welcome_page():
    """A simple welcome page to show after successful login."""
    st.title("Welcome!! 🥳🎉")
    st.write("You are logged in and ready to start your journey..")
    st.write("We've completed the database and authentication setup!")
    st.write("We can now move on to the next steps of building the journaling interface and AI integration.")
    st.write(f"Your User ID is: **{st.session_state.user_id}**")
    st.button("Start Journaling", use_container_width = True, on_click = lambda: st.session_state.update(page="journal"))

def main_app():
    """Handles page routing based on session state."""
    if st.session_state.page == "login":
        show_login_page()
    elif st.session_state.page == "set_security_key":
        show_set_security_key_page()
    elif st.session_state.page == "security_check":
        show_security_check_page()
    elif st.session_state_page == "welcome":
        show_welcome_page()
    #the 'journal' page will be addede in the next step
    #elif st.session_state.page == "journal":
    #    show_journal_page()
main_app()
