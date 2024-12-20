# Use an official Python runtime as a parent image
FROM python:3.6-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the local application code to the container
COPY . .

# Install any Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV DB_URL=postgresql://postgres:123@flask_db:5432/test

# Expose the application port
EXPOSE 8060

# Define the command to run the application
CMD ["python", "app.py", "--host=0.0.0.0", "--port=8060"]