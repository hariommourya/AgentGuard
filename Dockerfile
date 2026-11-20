FROM python:3.13-slim
WORKDIR /app
COPY app.py guard.py style.css ./
ENV PORT=8080
CMD ["python", "app.py"]
