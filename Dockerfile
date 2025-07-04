# Base image
FROM python:3.11-slim

# Create non-root user to avoid permission errors
RUN adduser --disabled-password --gecos '' appuser

# Set working directory
WORKDIR /home/appuser/app

# Set environment variables for Streamlit
ENV STREAMLIT_SERVER_PORT=7860
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Copy all files
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Make a writable .streamlit config directory
RUN mkdir -p /home/appuser/.streamlit
ENV STREAMLIT_CONFIG_DIR=/home/appuser/.streamlit

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 7860

# Final CMD
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
