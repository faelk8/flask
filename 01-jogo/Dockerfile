FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/jogoteca
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app
COPY --chown=app:app ./ ./
COPY --chown=app:app deploy/gunicorn.conf.py /srv/gunicorn.conf.py
COPY --chown=app:app deploy/start.sh /srv/start.sh
USER 10001:10001
EXPOSE 8000
CMD ["sh", "/srv/start.sh"]
