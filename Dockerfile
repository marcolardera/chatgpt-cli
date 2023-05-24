FROM python:3-slim

WORKDIR /app

COPY . ./

RUN pip install -r requirements.txt

WORKDIR /data

ENTRYPOINT ["python", "/app/chatgpt.py"]
