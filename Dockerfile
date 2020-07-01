FROM python:alpine

VOLUME /src/
COPY kc-utilities.py requirements.txt /src/
WORKDIR /src
RUN apk add --no-cache git
RUN pip install -r requirements.txt

CMD ["python", "-u", "/src/kc-utilities.py"]