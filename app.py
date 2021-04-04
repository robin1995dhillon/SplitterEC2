import os
import shutil
import subprocess

import boto3
from celery import Celery
from flask import Flask, request, json
from jproperties import Properties

app = Flask(__name__)
app.secret_key = os.urandom(24)

broker_url = 'amqp://guest@localhost'          # Broker URL for RabbitMQ task queue
celery = Celery(app.name, broker=broker_url)
celery.config_from_object('celeryconfig')

config = Properties()
with open('aws.properties', 'rb') as read:
    config.load(read)

aws_access_key_id = config.get("AWS_ACCESS_KEY_ID").data
aws_secret_access_key = config.get("AWS_SECRET_ACCESS_KEY").data
aws_session_token = config.get("AWS_SESSION_TOKEN").data

s3 = boto3.resource(service_name='s3',
                    region_name='us-east-1',
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    aws_session_token=aws_session_token)

sns = boto3.client('sns',
                   region_name='us-east-1',
                   aws_access_key_id=aws_access_key_id,
                   aws_secret_access_key=aws_secret_access_key,
                   aws_session_token=aws_session_token)

response = sns.list_topics()
topics = response["Topics"]
for arn in topics:
    # print(arn['TopicArn'])
    if 'dynamodb' not in arn['TopicArn']:
        continue
    else:
        topic_arn = arn['TopicArn']

@celery.task(bind=True)
def process_file(self, email, bucket, key):
    src_file = './src/' + key
    s3.Bucket(bucket).download_file(key, src_file)

    des_dir = './des/'

    command = f'spleeter separate  -o {des_dir} {src_file}'
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()

    output_path = './des/' + os.path.splitext(key)[0]
    shutil.make_archive(output_path, 'zip', output_path)

    upload_path = output_path + '.zip'
    s3.Bucket(bucket).upload_file(upload_path, key + '.zip')

    # Mail to user
    sendEmail(email, bucket, key)

@celery.task(bind=True)
def sendEmail(self, email, bucket, key):
    link = f'https://{bucket}.s3.amazonaws.com/{key}'
    email = email
    response_sns = sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=email)
    subscription_arn = response_sns["SubscriptionArn"]
    sns.publish(TopicArn=topic_arn,
                Message=f"Hi, here is your link to download {link}",
                Subject="Link to download")
    return 'mail sent'

@app.route('/', methods=['GET'])
def getHome():
    return "Server is up."

@app.route('/', methods=['POST'])
def postHome():
    email = request.form.get('email')
    bucket = request.form.get('bucket')
    key = request.form.get('key')

    process_file.delay(email, bucket, key)

    data = {"bucket": bucket, "key": key+'.zip'}

    response = app.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response