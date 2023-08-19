# syntax=docker/dockerfile:1
FROM python:3.10
WORKDIR /app
COPY . /app/.
RUN pip install --no-cache-dir -r /app/requirements.txt
FROM mysql:latest
COPY ./database.sql /docker-entrypoint-initdb.d/
CMD ["python", "run.py"]