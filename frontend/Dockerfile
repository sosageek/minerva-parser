FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY src ./src

EXPOSE 8004

CMD ["uvicorn", "src.frontend:app", "--host", "0.0.0.0", "--port", "8004"]
