import os
import shutil
import subprocess

import boto3
from flask import Flask, request, json
from jproperties import Properties

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

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/', methods=['GET'])
def getHome():
    return "Server is up."

@app.route('/', methods=['POST'])
def postHome():
    bucket = request.form.get('bucket')
    key = request.form.get('key')

    src_file = './src/'+key
    des_dir = './des/'

    print("download start")
    s3.Bucket(bucket).download_file(key, src_file)
    print("download done")

    print("separation start")
    command = f'spleeter separate  -o {des_dir} {src_file}'
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()
    print("separation done")

    output_path = './des/'+os.path.splitext(key)[0]
    shutil.make_archive(output_path, 'zip', output_path)

    upload_path = output_path + '.zip'
    s3.Bucket(bucket).upload_file(upload_path, key+'.zip')

    data = {"bucket": bucket, "key": key+'.zip'}

    response = app.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response
