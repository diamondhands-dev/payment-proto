from lnd_grpc import lightning_pb2 as ln
from lnd_grpc import lightning_pb2_grpc as lnrpc
import grpc
import os
import codecs
from os.path import join, dirname
from dotenv import load_dotenv
from google.protobuf.json_format import MessageToDict
import lnd_apiweb
import sys

load_dotenv(verbose=True)

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'

def metadata_callback(context, callback):
    callback([('macaroon', macaroon)], None)

endpoint = os.getenv("LND_GRPC_ENDPOINT")
port = int(os.getenv("LND_GRPC_PORT"))
cert = open(os.getenv("LND_GRPC_CERT"), 'rb').read()
with open(os.getenv("LND_GRPC_MACAROON"), 'rb') as f:
    macaroon_bytes = f.read()
    macaroon = codecs.encode(macaroon_bytes, 'hex')

cert_creds = grpc.ssl_channel_credentials(cert)
auth_creds = grpc.metadata_call_credentials(metadata_callback)
combined_creds = grpc.composite_channel_credentials(cert_creds, auth_creds)
channel = grpc.secure_channel(f"{endpoint}:{port}", combined_creds)
stub = lnrpc.LightningStub(channel)


import flask
from flask import render_template, request, send_from_directory
from flask import Flask, session
from flask_cors import CORS
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import uuid
import base64
import qrcode
import time
from io import BytesIO
from PIL import Image
from datetime import timedelta

from sqlalchemy import Column, Integer, String, DateTime, PickleType
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
Base = declarative_base()
from channel import Channel

def pil_to_base64(img):
    buffer = BytesIO()
    img.save(buffer, format="jpeg")
    img_str = base64.b64encode(buffer.getvalue()).decode("ascii")

    return img_str


app = flask.Flask(__name__, static_folder='static')
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)
Session(app)
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["2000 per day", "20 per minute"]
)
CORS(app)

@app.route('/')
def home():
    return render_template("index.html")


#無料情報１取得
@app.route('/req_a')
def req_a():
    print('requesting req_a...')

    request = ln.GetInfoRequest()
    response = stub.GetInfo(request)

    req_a = {
        "alias": response.alias,
        "public_key": response.identity_pubkey,
    }
    return req_a


#無料情報２取得
@app.route('/req_b')
def req_b():
    print('requesting req_b...')

    db_filename = 'sqlite:///' + os.path.join('./graph.db')

    engine = create_engine(db_filename, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker()
    Session.configure(bind=engine)
    s = Session()
    try:
        channels = s.query(Channel).all()
    except Exception as e:
        print("ERROR: {0}".format(sys.exc_info()[1]))
        print("ERROR: Try running channel.py first")
        exit()

    req_b = {}
    for i in range(len(channels)):
        req_b[i] = {
            "channel_id": str(channels[i].channel_id),
            "alias": channels[i].node2_alias,
            "capacity": channels[i].capacity,
            "remote_pubkey": channels[i].node2_pub,
            "node1_pkey": channels[i].node1_pub,
            "node1_base_fee": channels[i].node1_base_fee,
            "node1_fee_rate": channels[i].node1_fee_rate,
            "node2_pkey": channels[i].node2_pub,
            "node2_base_fee": channels[i].node2_base_fee,
            "node2_fee_rate": channels[i].node2_fee_rate,
        }

    return req_b



#インボイス発行
@app.route('/req_c/<channel_id>')
def req_c(channel_id):
    return lnd_apiweb.createInvoice(channel_id)


#支払いチェック＆有料情報取得
@app.route('/req_d')
@limiter.limit("20 per minute")
def req_d():
    return lnd_apiweb.checkInvoice()


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/img'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.errorhandler(Exception)
def server_error(err):
    print(err)
    return "Some general exception", 500


if __name__ == '__main__':
    print('Starting server on port {port}'.format(
        port=port
    ))
    app.config['SECRET_KEY'] = os.getenv(
        "REQUEST_INVOICE_SECRET",
        default=uuid.uuid4())
    app.debug = True
    app.run(host='0.0.0.0', port=8810)

