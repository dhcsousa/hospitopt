# Dockerfile for Reflex backend (handles WebSocket state management AND serves frontend)
FROM python:3.14-slim

# Install system dependencies required by reflex
RUN apt-get update && apt-get install -y --no-install-recommends \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the frontend directory
COPY . .

# Install app requirements
RUN pip install -r requirements.txt

# Initialize Reflex
RUN reflex init

# Remove existing symlinks to prevent conflicts on container restart
RUN rm -rf /app/assets/external/*

# Expose ports for Reflex (backend on 8000, frontend on 3000)
EXPOSE 8000 3000

# Run the full Reflex app (backend + frontend serving)
CMD ["reflex", "run", "--env", "prod", "--loglevel", "info"]
