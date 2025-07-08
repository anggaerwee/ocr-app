# Gunakan Python image
FROM python:3.13-slim

# Buat working directory
WORKDIR /app

# Copy semua file ke container
COPY . .

# Install dependency
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variable Flask
ENV PYTHONUNBUFFERED=True

# Jalankan app.py dengan gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
