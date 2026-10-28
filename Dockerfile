FROM python:3.13-alpine
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY bot.py .
USER nobody
CMD ["python", "bot.py"]
