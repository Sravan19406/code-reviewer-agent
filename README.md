<img width="1487" height="382" alt="image" src="https://github.com/user-attachments/assets/3a40e4c2-1972-4083-8ead-b6b95c151917" /># study-buddy

# 🐞 Code Reviewer Agent

An AI agent that runs your Python code, finds bugs, writes a fix, and re-runs it to verify.

**Deploy on Streamlit Community Cloud**
1. Push these files (`app.py`, `requirements.txt`) to a GitHub repo.
2. At share.streamlit.io click Create app, pick the repo, set main file to `app.py`.
3. In Advanced settings > Secrets add: `GEMINI_API_KEY = "your-key"`
4. Deploy.

Optional secrets: `APP_PASSWORD` (recommended, since this app executes pasted code), `GEMINI_MODEL`.
