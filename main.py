import subprocess
import os
import sys

def launch_app():
    app_path = os.path.join(os.path.dirname(__file__), "app.py")

    if not os.path.exists(app_path):
        print(f"❌ Could not find app.py at {app_path}")
        sys.exit(1)

    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", app_path])
    except Exception as e:
        print(f"❌ Failed to launch Streamlit: {e}")
        sys.exit(1)

if __name__ == "__main__":
    launch_app()
