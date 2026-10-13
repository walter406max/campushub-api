import streamlit as st

def apply_theme():
    st.markdown("""
<style>

    /* ==============================
       GLOBAL PAGE
    ============================== */

    .stApp {
        background: #f4f6fb;
    }

    header[data-testid="stHeader"] {
        background: transparent;
    }

    footer {
        visibility: hidden;
    }


    /* Remove Streamlit default spacing */

    .block-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        max-width: 100% !important;
    }


    /* ==============================
       MAIN LOGIN CARD
    ============================== */

    .login-card {
        width: 92%;
        max-width: 1050px;
        min-height: 650px;

        margin: 50px auto;

        background: white;

        border-radius: 18px;

        overflow: hidden;

        box-shadow:
            0 20px 50px rgba(0, 0, 0, 0.12);

        display: flex;
    }


    /* ==============================
       LEFT BLUE CAMPUSHUB PANEL
    ============================== */

    .brand-panel {

        width: 48%;

        min-height: 650px;

        position: relative;

        overflow: hidden;

        background:
            linear-gradient(
                135deg,
                #08a9df 0%,
                #119ed7 50%,
                #25afe2 100%
            );

        color: white;

        display: flex;

        align-items: center;

        justify-content: center;

    }


    /* Decorative diagonal shape */

    .brand-panel::after {

        content: "";

        position: absolute;

        width: 700px;
        height: 700px;

        background: rgba(255,255,255,0.05);

        transform: rotate(35deg);

        bottom: -450px;

        left: -150px;

    }


    /* ==============================
       BRANDING
    ============================== */

    .brand-content {

        position: relative;

        z-index: 5;

        width: 78%;

        margin-top: 80px;

    }

    .brand-content h1 {

        font-size: 45px;

        font-weight: 700;

        margin: 0 0 8px 0;

        letter-spacing: -1px;

    }

    .brand-content p {

        font-size: 20px;

        font-weight: 600;

        margin: 0;

    }


    /* ==============================
       FLOATING EDUCATION ICONS
    ============================== */

    .edu-icon {

        position: absolute;

        z-index: 3;

        width: 65px;
        height: 65px;

        border-radius: 50%;

        display: flex;

        justify-content: center;

        align-items: center;

        color: white;

        font-size: 27px;

        background: rgba(255,255,255,0.13);

        border: 2px solid rgba(255,255,255,0.22);

        box-shadow:
            0 5px 20px rgba(0,0,0,0.05);

    }


    .cap {
        top: 90px;
        left: 80px;
    }

    .book1 {
        top: 175px;
        left: -20px;

        width: 95px;
        height: 95px;

        font-size: 40px;
    }

    .pencil1 {
        top: 200px;
        left: 150px;
    }

    .star {
        top: 300px;
        left: -20px;
    }

    .book2 {
        bottom: 160px;
        left: -20px;

        width: 95px;
        height: 95px;

        font-size: 40px;
    }

    .pencil2 {
        bottom: 170px;
        left: 140px;
    }

    .flask {
        bottom: 55px;
        left: 75px;

        width: 70px;
        height: 70px;

        font-size: 32px;
    }


    /* ==============================
       DECORATIVE DOTS
    ============================== */

    .dots {

        position: absolute;

        bottom: 35px;

        left: 50%;

        transform: translateX(-50%);

        color: rgba(255,255,255,0.25);

        font-size: 20px;

        letter-spacing: 5px;

        line-height: 10px;

    }


    /* ==============================
       RIGHT LOGIN PANEL
    ============================== */

    .login-panel {

        width: 52%;

        background: white;

        padding: 70px 65px;

    }


    /* ==============================
       LOGIN TITLE
    ============================== */

    .login-title {

        font-size: 35px;

        font-weight: 700;

        color: #111827;

        margin: 0;

    }

    .login-subtitle {

        font-size: 16px;

        color: #222;

        margin-top: 8px;

        margin-bottom: 42px;

    }


    /* ==============================
       STREAMLIT INPUTS
    ============================== */

    div[data-testid="stTextInput"] label {

        font-weight: 600;

        color: #111827;

        font-size: 14px;

    }

    div[data-testid="stTextInput"] input {

        height: 52px !important;

        border-radius: 10px !important;

        border: 1px solid #c9c9c9 !important;

        padding-left: 17px !important;

        box-shadow:
            0 3px 8px rgba(0,0,0,0.05);

        font-size: 15px !important;

    }

    div[data-testid="stTextInput"] input:focus {

        border-color: #10a6dc !important;

        box-shadow:
            0 0 0 2px rgba(16,166,220,0.12) !important;

    }


    /* ==============================
       BUTTON
    ============================== */

    div.stButton > button {

        width: 100% !important;

        height: 52px !important;

        border-radius: 30px !important;

        background: #10a6dc !important;

        color: white !important;

        border: none !important;

        font-size: 18px !important;

        font-weight: 700 !important;

        box-shadow:
            0 5px 15px rgba(16,166,220,0.25);

        transition: all 0.2s ease;

    }


    div.stButton > button:hover {

        background: #0798cd !important;

        transform: translateY(-1px);

    }


    /* ==============================
       CHECKBOX
    ============================== */

    div[data-testid="stCheckbox"] label {

        font-size: 14px;

    }


    /* ==============================
       LINKS
    ============================== */

    .forgot {

        text-align: right;

        margin-top: -42px;

        margin-bottom: 25px;

    }

    .forgot a {

        color: #159dc9;

        text-decoration: none;

        font-size: 14px;

        font-weight: 600;

    }


    /* ==============================
       SIGN UP
    ============================== */

    .signup {

        text-align: center;

        margin-top: 25px;

        color: #111;

        font-size: 15px;

    }

    .signup a {

        display: block;

        margin-top: 10px;

        color: #119bc6;

        font-size: 17px;

        font-weight: 700;

        text-decoration: none;

    }


    /* ==============================
       MOBILE
    ============================== */

    @media (max-width: 800px) {

        .login-card {

            width: 95%;

            margin: 20px auto;

            display: block;

        }

        .brand-panel {

            width: 100%;

            min-height: 270px;

        }

        .login-panel {

            width: 100%;

            padding: 40px 30px;

        }

        .brand-content {

            text-align: center;

            margin-top: 60px;

        }

        .brand-content h1 {

            font-size: 36px;

        }

        .brand-content p {

            font-size: 17px;

        }

        .book2,
        .pencil2,
        .flask,
        .star {

            display: none;

        }

    }


    @media (max-width: 500px) {

        .login-card {

            width: 100%;

            margin: 0;

            border-radius: 0;

        }

        .brand-panel {

            min-height: 230px;

        }

        .login-panel {

            padding: 35px 22px;

        }

        .login-title {

            font-size: 29px;

        }

    }

</style>
""", unsafe_allow_html=True)


# ============================================================
# LOGIN CARD
# ============================================================

st.markdown("""

<div class="login-card">

    <!-- LEFT SIDE -->

    <div class="brand-panel">

        <div class="edu-icon cap">
            🎓
        </div>

        <div class="edu-icon book1">
            📖
        </div>

        <div class="edu-icon pencil1">
            ✏️
        </div>

        <div class="edu-icon star">
            ⭐
        </div>

        <div class="edu-icon book2">
            📖
        </div>

        <div class="edu-icon pencil2">
            ✏️
        </div>

        <div class="edu-icon flask">
            🧪
        </div>


        <div class="brand-content">

            <h1>CampusHub</h1>

            <p>Your Campus, Connected.</p>

        </div>


        <div class="dots">
            • • • • •
            <br>
            • • • • •
        </div>

    </div>


    <!-- RIGHT SIDE -->

    <div class="login-panel">

        <h1 class="login-title">
            Welcome Back
        </h1>

        <p class="login-subtitle">
            Sign in to continue to CampusHub
        </p>

</div>

""", unsafe_allow_html=True)


# ============================================================
# STREAMLIT LOGIN FORM
# ============================================================

# Create the right-side form using Streamlit
col1, col2 = st.columns([0.01, 0.98])

with col2:

    email = st.text_input(
        "Email Address",
        placeholder="student@university.edu",
        label_visibility="visible"
    )

    password = st.text_input(
        "Password",
        placeholder="••••••••",
        type="password"
    )

    # Options
    remember_col, forgot_col = st.columns([1, 1])

    with remember_col:

        remember = st.checkbox("Remember me")

    with forgot_col:

        st.markdown(
            """
            <div class="forgot">
                <a href="#">Forgot password?</a>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Login button
    if st.button("Log In", use_container_width=True):

        if email and password:

            st.success("Login successful!")

        else:

            st.error("Please enter your email and password.")

    # Signup
    st.markdown(
        """
        <div class="signup">

            <div>Don't have an account?</div>

            <a href="#">
                Sign Up
            </a>

        </div>
        """,
        unsafe_allow_html=True
    )


# Close card
st.markdown("""
    </div>
</div>
""", unsafe_allow_html=True)
