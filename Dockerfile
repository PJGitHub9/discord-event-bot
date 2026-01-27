# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot files
COPY bot.py .
COPY database.py .

# Create directory for database
RUN mkdir -p /app/data

# Environment variables will be passed at runtime
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "bot.py"]
