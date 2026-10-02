FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /app
RUN useradd --create-home --uid 10001 tracker && chown -R tracker:tracker /app
USER tracker
EXPOSE 8765
CMD ["python3", "server.py"]
