# Use the official slim Python image
FROM python:3.10-slim

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY a.py .

# Expose logs
VOLUME ["/app/bot.log"]

# Run the bot
CMD ["python", "a.py"]