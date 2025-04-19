GNU nano 7.2                                                                                                    Dockerfile                                                                                                              
FROM python:3.13-alpine
COPY ./requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install -r requirements.txt
COPY . /app
EXPOSE 5000
ENTRYPOINT ["python"]
CMD ["app.py"]