FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the application port
EXPOSE 8080

# Command to run the app with gunicorn
CMD ["gunicorn", "-w", "2", "--threads", "10", "--timeout", "300", "-b", "0.0.0.0:8080", "app:app"] 