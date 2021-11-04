from lnd_grpc import lightning_pb2 as ln
from lnd_grpc import lightning_pb2_grpc as lnrpc

import base64
import os
import codecs
import grpc

from os.path import join, dirname
from dotenv import load_dotenv
load_dotenv(verbose=True)
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

endpoint = os.getenv("LND_GRPC_ENDPOINT")
port = int(os.getenv("LND_GRPC_PORT"))

MESSAGE_SIZE_MB = 50 * 1024 * 1024

class Lnd:
    def __init__(self):
        os.environ['GRPC_SSL_CIPHER_SUITES'] = 'HIGH+ECDSA'
        combined_creds = self.get_credentials(os.getenv("LND_GRPC_MACAROON"))
        channel_options = [
            ('grpc.max_message_length', MESSAGE_SIZE_MB),
            ('grpc.max_receive_message_length', MESSAGE_SIZE_MB)
        ]
        grpc_channel = grpc.secure_channel(f"{endpoint}:{port}", combined_creds, channel_options)

        self.stub = lnrpc.LightningStub(grpc_channel)
        self.info = None
        self.channels = None
        self.valid = True
        try:
            self.info = self.get_info()
        except grpc._channel._InactiveRpcError:
            self.valid = False

    @staticmethod
    def get_credentials(macaroon_path):
        tls_cert = open(os.getenv("LND_GRPC_CERT"), 'rb').read()
        ssl_credentials = grpc.ssl_channel_credentials(tls_cert)
        macaroon = codecs.encode(open(macaroon_path, 'rb').read(), 'hex')
        auth_credentials = grpc.metadata_call_credentials(lambda _, callback: callback([('macaroon', macaroon)], None))
        combined_credentials = grpc.composite_channel_credentials(ssl_credentials, auth_credentials)
        return combined_credentials

    def get_info(self):
        if self.info is None:
            self.info = self.stub.GetInfo(ln.GetInfoRequest())
        return self.info

    def get_own_pubkey(self):
        return self.get_info().identity_pubkey

    def get_channels(self):
        if self.channels is None:
            request = ln.ListChannelsRequest()
            self.channels = self.stub.ListChannels(request)
        return self.channels
    
    def get_nodeinfo(self, pubkey):
        request = ln.NodeInfoRequest(
            pub_key = pubkey,
            include_channels = True,
        )
        self.nodeinfo = self.stub.GetNodeInfo(request)
        return self.nodeinfo