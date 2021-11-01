from lnd_grpc import lightning_pb2 as ln
from lnd_grpc import lightning_pb2_grpc as lnrpc
import grpc

import os
import codecs
from os.path import join, dirname
from dotenv import load_dotenv
from flask import session
import base64
import qrcode
from io import BytesIO
from PIL import Image

load_dotenv(verbose=True)

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'

def metadata_callback(context, callback):
    callback([('macaroon', macaroon)], None)
def metadata_callback_invoice(context, callback):
    callback([('macaroon', macaroon_invoice)], None)

endpoint = os.getenv("LND_GRPC_ENDPOINT")
port = int(os.getenv("LND_GRPC_PORT"))
cert = open(os.getenv("LND_GRPC_CERT"), 'rb').read()
with open(os.getenv("LND_GRPC_MACAROON"), 'rb') as f:
    macaroon_bytes = f.read()
    macaroon = codecs.encode(macaroon_bytes, 'hex')
with open(os.getenv("LND_GRPC_MACAROON_INVOICE"), 'rb') as f:
    macaroon_bytes = f.read()
    macaroon_invoice = codecs.encode(macaroon_bytes, 'hex')

cert_creds = grpc.ssl_channel_credentials(cert)
auth_creds = grpc.metadata_call_credentials(metadata_callback)
combined_creds = grpc.composite_channel_credentials(cert_creds, auth_creds)
channel = grpc.secure_channel(f"{endpoint}:{port}", combined_creds)
stub = lnrpc.LightningStub(channel)

auth_creds = grpc.metadata_call_credentials(metadata_callback_invoice)
combined_creds = grpc.composite_channel_credentials(cert_creds, auth_creds)
channel = grpc.secure_channel(f"{endpoint}:{port}", combined_creds)
stub_invoice = lnrpc.LightningStub(channel)


def pil_to_base64(img):
    buffer = BytesIO()
    img.save(buffer, format="jpeg")
    img_str = base64.b64encode(buffer.getvalue()).decode("ascii")

    return img_str


#----------------------------------------------------
#インボイス発行
#----------------------------------------------------
def createInvoice(channel_id):
    print('createInvoice...')

    #channel_idセションセット
    session["channel_id"] = channel_id

    amount = 150
    description = "Peek DH channel_id: " + str(channel_id)

    response = stub_invoice.AddInvoice(ln.Invoice(value=amount,memo=description,))
    img = qrcode.make(response.payment_request)
    imgStr = "data:image/jpeg;base64," + pil_to_base64(img)

    #payment_hashセションセット
    session["payment_hash"] = response.r_hash.hex()

    resCreateInvoice = {
        "bolt11": response.payment_request,
        "qrStr": imgStr,
    }

    #debug
    print("channel_id1:" + session["channel_id"])
    print("payment_hash1:" + session["payment_hash"])

    return resCreateInvoice


#----------------------------------------------------
#支払い確認＆ノードバランス取得
#----------------------------------------------------
def checkInvoice():
    print('checkInvoice...')

    request = ln.PaymentHash(
        r_hash_str = session["payment_hash"],
    )
    response = stub.LookupInvoice(request)

    if(response.state == 1):
        request2 = ln.ListChannelsRequest()
        response2 = stub.ListChannels(request2)

        for i in range(len(response2.channels)):
            if(str(response2.channels[i].chan_id) == session["channel_id"]):
                resCheckInvoice = {
                    "capacity": response2.channels[i].capacity,
                    "localBalance": response2.channels[i].local_balance,
                    "remoteBalance": response2.channels[i].remote_balance,
                }

                #debug
                print("channel_id2:" + session["channel_id"])
                print("payment_hash2:" + session["payment_hash"])

                #全セション変数クリア
                session["channel_id"] = ""
                session["payment_hash"] = ""

                #debug
                print("channel_id3:" + session["channel_id"])
                print("payment_hash3:" + session["payment_hash"])
                return resCheckInvoice

        return "ERROR"

    else:
        return ""
