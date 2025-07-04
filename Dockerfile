FROM python:3.11-slim

# Create a user with home directory
RUN useradd -ms /bin/bash appuser

# Set home and work dir
ENV HOME=/home/appuser
WORKDIR /home/appuser/app

# Set up Streamlit config directory
ENV STREAMLIT_HOME=$HOME/.streamlit
RUN mkdir -p $STREAMLIT_HOME

# Install system deps and app deps
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY . .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 7860

# Run Streamlit with correct config
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]