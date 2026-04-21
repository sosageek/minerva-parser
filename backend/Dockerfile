FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

RUN python -m playwright install --with-deps chromium

COPY src ./src

EXPOSE 8003

CMD ["uvicorn", "src.server.server:app", "--host", "0.0.0.0", "--port", "8003"]