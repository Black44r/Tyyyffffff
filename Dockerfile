# Use the official slim Python image
FROM python:3.10-slim

# Set work directory
WORKDIR /app

# Upgrade pip and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy bot code
# Ensure your main script is named main.py
COPY main.py .

# Run the bot
CMD ["python", "main.py"]
