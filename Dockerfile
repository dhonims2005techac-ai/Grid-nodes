FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir dispy pycos flask requests

COPY worker.py .
COPY master.py .

EXPOSE 8080
EXPOSE 51348

CMD ["python", "worker.py"]
