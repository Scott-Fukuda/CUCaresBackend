from flask_cors import CORS 

# restrict API access to requests from secure origin
def init_cors(app, env):
    if env == "staging":
        CORS(app, origins=["http://localhost:5173", "http://127.0.0.1:5173", "https://campuscares.us", "https://www.campuscares.us"], supports_credentials=True)
    else: 
        CORS(app, origins=["https://campuscares.us", "https://www.campuscares.us", "https://cu-cares-frontend-git-feature-multiopp-scotts-projects-851bba1b.vercel.app", "https://cu-cares-frontend-git-feature-e-cb5fc1-scotts-projects-851bba1b.vercel.app"], supports_credentials=True)

    # CORS(app, origins=["https://campuscares.us", "https://www.campuscares.us", "http://localhost:5173"], supports_credentials=True)
