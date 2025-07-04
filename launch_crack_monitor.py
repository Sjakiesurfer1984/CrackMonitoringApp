
import subprocess
import sys
import os
import webbrowser

def ensure_package(package):
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def launch_streamlit():
    app_path = os.path.join(os.path.dirname(__file__), "app.py")
    subprocess.Popen(["streamlit", "run", app_path])
    webbrowser.open("http://localhost:8501")

if __name__ == "__main__":
    ensure_package("streamlit")
    ensure_package("plotly")
    launch_streamlit()
