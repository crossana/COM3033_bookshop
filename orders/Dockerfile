# Start from an official image that already has Python installed
FROM python:3.12-slim

# All following commands run inside /app in the image
WORKDIR /app

# Install the dependencies first so that this layer can be cached
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy in the rest of our code
COPY . .

# Configuration for this service
ENV PORT=5002
EXPOSE 5002

# The command that runs when a container starts
CMD ["python", "app.py"]
