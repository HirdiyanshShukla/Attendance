FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl wget unzip gnupg npm chromium chromium-driver \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set chromium binary for Selenium
ENV CHROME_BIN=/usr/bin/chromium
ENV PATH="${PATH}:/usr/bin/chromium"

WORKDIR /app

# Copy all files
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Build Tailwind CSS via npm (inside django-tailwind app)
WORKDIR /app/theme  # 🔁 Replace "theme" if your tailwind app has a different name
RUN npm install
RUN npm run build

# Return to app root
WORKDIR /app

# Expose Django port
EXPOSE 8000

# Start Gunicorn with Django wsgi
CMD ["gunicorn", "att_scrape.wsgi:application", "--bind", "0.0.0.0:8000"]
