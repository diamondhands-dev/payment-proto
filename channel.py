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
channel = grpc.secure_channel(f"{endpoint}:{port}", combined_creds, options=[('grpc.max_receive_message_length',1024*1024*50)])
stub = lnrpc.LightningStub(channel)

my_node_id = stub.GetInfo(ln.GetInfoRequest()).identity_pubkey
my_alias = stub.GetInfo(ln.GetInfoRequest()).alias

from sqlalchemy import Column, Integer, String, DateTime, PickleType
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class Info(Base):
    __tablename__ = "info"
    identity_pubkey = Column(String, primary_key=True)
    alias = Column(String)

    def __init__(self, identity_pubkey, alias):
        self.identity_pubkey = identity_pubkey
        self.alias = alias

class Channel(Base):
    __tablename__ = "channel"
    channel_id = Column(Integer, primary_key=True)
    capacity = Column(Integer)
    node1_pub = Column(String)
    node1_base_fee = Column(Integer)
    node1_fee_rate = Column(Integer)
    node2_pub = Column(String)
    node2_alias = Column(String)
    node2_base_fee = Column(Integer)
    node2_fee_rate = Column(Integer)

    def __init__(self, channel_id, capacity, node1_pub, node1_base_fee, node1_fee_rate, node2_pub, node2_alias, node2_base_fee, node2_fee_rate):
        self.channel_id = channel_id
        self.capacity = capacity
        self.node1_pub = node1_pub
        self.node1_base_fee = node1_base_fee
        self.node1_fee_rate = node1_fee_rate
        self.node2_pub = node2_pub
        self.node2_alias = node2_alias
        self.node2_base_fee = node2_base_fee
        self.node2_fee_rate = node2_fee_rate

def getInfo(engine):

    Session = sessionmaker()
    Session.configure(bind=engine)
    s = Session()
    s.query(Info).delete()
    s.commit()

    info = Info(
                my_node_id,
                my_alias,
    )
    s.add(info)
    s.commit()

def getChannels(engine):

    Session = sessionmaker()
    Session.configure(bind=engine)
    s = Session()
    s.query(Channel).delete()
    s.commit()

    request = ln.ListChannelsRequest()
    response = stub.ListChannels(request)
    pubkeys = list(set([ sub.remote_pubkey for sub in response.channels ]))
    channels = list(set([ sub.chan_id for sub in response.channels ]))

    for i in range(len(pubkeys)):
        
        request2 = ln.NodeInfoRequest(
            pub_key = pubkeys[i],
            include_channels = True,
        )
        response2 = stub.GetNodeInfo(request2)

        for chan in response2.channels:
            if (chan.channel_id not in channels):
                continue
            if(chan.node1_pub == my_node_id):
                channel = Channel(
                                chan.channel_id,
                                chan.capacity,
                                chan.node1_pub,
                                chan.node1_policy.fee_base_msat,
                                chan.node1_policy.fee_rate_milli_msat,
                                chan.node2_pub,
                                response2.node.alias,
                                chan.node2_policy.fee_base_msat,
                                chan.node2_policy.fee_rate_milli_msat,
                )
                s.add(channel)
            elif(chan.node2_pub == my_node_id):
                channel = Channel(
                                chan.channel_id,
                                chan.capacity,
                                chan.node2_pub,
                                chan.node2_policy.fee_base_msat,
                                chan.node2_policy.fee_rate_milli_msat,
                                chan.node1_pub,
                                response2.node.alias,
                                chan.node1_policy.fee_base_msat,
                                chan.node1_policy.fee_rate_milli_msat,
                )
                s.add(channel)
    s.commit()

def batch():
    db_filename = 'sqlite:///' + os.path.join('./graph.db')
    engine = create_engine(db_filename, echo=True)
    Base.metadata.create_all(engine)
    getInfo(engine)
    getChannels(engine)

if __name__ == "__main__":
    db_filename = 'sqlite:///' + os.path.join('./graph.db')
    engine = create_engine(db_filename, echo=True)
    Base.metadata.create_all(engine)
    getInfo(engine)
    getChannels(engine)