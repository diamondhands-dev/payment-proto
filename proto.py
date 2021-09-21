from lnd_grpc import lightning_pb2 as ln
from lnd_grpc import lightning_pb2_grpc as lnrpc
import grpc
import os
import codecs

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
@app.route('/invoice/<int:amount>/<description>')
def getinvoice(amount, description):
    print('getinvoice...')

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

    request = ln.ChannelGraphRequest()
    response = stub.DescribeGraph(request)

    return str(response)


@app.route('/req_c')
def req_c():
    print('requesting req_c...')

    request = ln.ListChannelsRequest()
    response = stub.ListChannels(request)

    req_c = {}
    for i in range(len(response.channels)):
        req_c[i] = {
            "capacity": response.channels[i].capacity,
            "remote_pubkey": response.channels[i].remote_pubkey,
        }

    return req_c
    #return str(response)


@app.route('/req_d/<payment_hash>/<public_key>/<body_index>')
def req_d(payment_hash, public_key, body_index):
    print('requesting req_d...')

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
                if(response2.channels[i].remote_pubkey == public_key):
                    req_d = {
                        "capacity": response2.channels[i].capacity,
                        "local_balance": response2.channels[i].local_balance,
                        "remote_balance": response2.channels[i].remote_balance,
                        "body_index": body_index,
                    }
                    return req_d
        
            return "ERROR"
        else:
            return "ERROR"

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

