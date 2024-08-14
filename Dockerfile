# Use an official Python runtime as a parent image
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "chatgpt.chatgpt"]
