FROM python:3
MAINTAINER Shiqan

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8888
CMD [ "python", "./app.py" ]
