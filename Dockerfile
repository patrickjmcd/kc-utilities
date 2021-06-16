FROM python:3

WORKDIR /app
ADD kc_utilities .
RUN pip install -r requirements.txt

CMD ["python3", "main.py"]