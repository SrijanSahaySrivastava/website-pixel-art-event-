# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Redis
RUN apt-get update && apt-get install -y redis-server

# Expose the port the app runs on
EXPOSE 8000
EXPOSE 8001

# Start Redis server
RUN service redis-server start

# Initialize the database
RUN python database.py

# Command to run the FastAPI app and the website server
CMD ["sh", "-c", "service redis-server start && uvicorn app:app --host 0.0.0.0 --port 8000 --reload & python serve.py"]