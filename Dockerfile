# Use a lightweight Python base
FROM python:3.10-slim

# Install system-level Graphviz (CRITICAL for your app to draw SVGs)
RUN apt-get update && apt-get install -y graphviz

# Set up the working directory
WORKDIR /app

# Copy the requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your code into the server
COPY . .

# Expose the port Render uses
EXPOSE 10000

# Start the app using gunicorn
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:10000", "app:app"]
