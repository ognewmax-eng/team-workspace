FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/app/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -u 10001 -m workspace && mkdir /app/data && chown workspace /app/data
COPY --chown=workspace:workspace . .
USER workspace
EXPOSE 8000
CMD ["sh", "deploy/start.sh"]
