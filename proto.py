from lnd_grpc import lightning_pb2 as ln
from lnd_grpc import lightning_pb2_grpc as lnrpc
import grpc
import os
import codecs
from os.path import join, dirname
from dotenv import load_dotenv
from google.protobuf.json_format import MessageToDict

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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import uuid
import base64
import qrcode
import time
from io import BytesIO
from PIL import Image


def pil_to_base64(img):
    buffer = BytesIO()
    img.save(buffer, format="jpeg")
    img_str = base64.b64encode(buffer.getvalue()).decode("ascii")

    return img_str


app = flask.Flask(__name__, static_folder='static')
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["2000 per day", "20 per minute"]
)


@limiter.limit("20 per minute")
@app.route('/invoice/<channel_id>')
def getinvoice(channel_id):
    print('getinvoice...')
    amount = 150
    description = channel_id

    # Call LND gRPC
    response = stub.AddInvoice(ln.Invoice(value=amount,memo=description,))
    img = qrcode.make(response.payment_request)
    imgStr = "data:image/jpeg;base64," + pil_to_base64(img)

    invoice = {
        "bolt11": response.payment_request,
        "payment_hash": response.r_hash.hex(),
        "qr_str": imgStr,
    }
    return invoice


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
    #return str(response)


@app.route('/req_b')
def req_b():
    print('requesting req_b...')

    request = ln.ListChannelsRequest()
    response = stub.ListChannels(request)

    req_b = {}
    for i in range(len(response.channels)):
        request2 = ln.NodeInfoRequest(
            pub_key = response.channels[i].remote_pubkey,
            include_channels = False,
        )
        response2 = stub.GetNodeInfo(request2)

        request3 = ln.ChanInfoRequest(
            chan_id = response.channels[i].chan_id,
        )
        response3 = stub.GetChanInfo(request3)

        req_b[i] = {
            "channel_id": str(response.channels[i].chan_id),
            "alias": response2.node.alias,
            "capacity": response.channels[i].capacity,
            "remote_pubkey": response.channels[i].remote_pubkey,
            "node1_pkey": response3.node1_pub,
            "node1_base_fee": response3.node1_policy.fee_base_msat,
            "node1_fee_rate": response3.node1_policy.fee_rate_milli_msat,
            "node2_pkey": response3.node2_pub,
            "node2_base_fee": response3.node2_policy.fee_base_msat,
            "node2_fee_rate": response3.node2_policy.fee_rate_milli_msat,
        }

    return req_b
    #return str(response)


@app.route('/check/<payment_hash>/<body_index>')
def checkinvoice(payment_hash, body_index):
    print('requesting req_c...')

    request = ln.PaymentHash(
        r_hash_str = payment_hash,
    )
    response = stub.LookupInvoice(request)

    if(response.state == 1):
        print(int(time.time()) - int(response.settle_date))
        if((int(time.time()) - int(response.settle_date)) < 45):
            request2 = ln.ListChannelsRequest()
            response2 = stub.ListChannels(request2)

            for i in range(len(response2.channels)):
                if(str(response2.channels[i].chan_id) == response.memo):
                    req_c = {
                        "capacity": response2.channels[i].capacity,
                        "local_balance": response2.channels[i].local_balance,
                        "remote_balance": response2.channels[i].remote_balance,
                        "body_index": body_index,
                    }
                    return req_c
        
            return "ERROR"
        else:
            return "expired"

    else:
        return ""


@app.route('/')
def home():
    return render_template("index.html")


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

