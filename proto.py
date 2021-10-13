from lnd_grpc import lightning_pb2 as ln
from lnd_grpc import lightning_pb2_grpc as lnrpc
import grpc
import os
import codecs
from os.path import join, dirname
from dotenv import load_dotenv
from google.protobuf.json_format import MessageToDict

import lnd_apiweb

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
@app.route('/self')
def req_self():
    print('requesting my node info ...')

    request = ln.GetInfoRequest()
    response = stub.GetInfo(request)

    output = {
        "alias": response.alias,
        "publicKey": response.identity_pubkey,
    }
    return output


#無料情報２取得
@app.route('/channels')
def req_channels():
    print('requesting channels...')

    db_filename = 'sqlite:///' + os.path.join('./graph.db')

    engine = create_engine(db_filename, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker()
    Session.configure(bind=engine)
    s = Session()
    channels = s.query(Channel).all()
    
    output = {}
    for i in range(len(channels)):
        output[i] = {
            "channelId": str(channels[i].channel_id),
            "alias": channels[i].node2_alias,
            "capacity": channels[i].capacity,
            #"remotePubKey": channels[i].node2_pub,
            #"node1PubKey": channels[i].node1_pub,
            "node1BaseFee": channels[i].node1_base_fee,
            "node1FeeRate": channels[i].node1_fee_rate,
            "node2PubKey": channels[i].node2_pub,
            "node2BaseFee": channels[i].node2_base_fee,
            "node2FeeRate": channels[i].node2_fee_rate,
        }

    return output 



#インボイス発行
@app.route('/invoice/<channel_id>')
def req_invoice(channel_id):
    return lnd_apiweb.createInvoice(channel_id)


#支払いチェック＆有料情報取得
@app.route('/checkInvoice')
@limiter.limit("20 per minute")
def req_checkInvoice():
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

