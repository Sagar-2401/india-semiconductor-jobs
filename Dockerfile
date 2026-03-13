FROM python:3.11-slim

WORKDIR /app

# Copy requirement files first
COPY backend/requirements.txt ./backend/
COPY scraper/requirements.txt ./scraper/

# Install dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt -r scraper/requirements.txt

# Copy the rest of the application
COPY . .

# Background jobs need apscheduler to run inside FastAPI natively
RUN pip install apscheduler

# Make sure ports are accessible and standard Render PORT is respected
EXPOSE 8000

# Specify start command explicitly
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
