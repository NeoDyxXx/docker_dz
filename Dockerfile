FROM python:3.9
RUN mkdir /opt/app
WORKDIR /opt/app

RUN pip install --upgrade pip
RUN pip install pysqlite3
RUN pip install requests
RUN pip install flask
RUN pip install flask_login
RUN pip install oauthlib
RUN pip install pyopenssl

COPY app/ /opt/app

EXPOSE 5000
CMD ["python", "./app.py"]