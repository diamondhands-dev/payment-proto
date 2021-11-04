from lnd import Lnd
import sys
import os

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
    node1_pub = Column(String) # my node id
    node1_base_fee = Column(Integer)
    node1_fee_rate = Column(Integer)
    node2_pub = Column(String) # remote node id
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

def debug(message):
    sys.stderr.write(message + "\n")

def getInfo(engine, lnd):

    my_node_id = lnd.get_info().identity_pubkey
    my_alias = lnd.get_info().alias

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

def getChannels(engine, lnd):

    Session = sessionmaker()
    Session.configure(bind=engine)
    s = Session()
    s.query(Channel).delete()
    s.commit()

    channels = lnd.get_channels().channels
    pubkeys = list(set([ chan.remote_pubkey for chan in channels ]))
    my_channels = list(set([ chan.chan_id for chan in channels ]))

    for i in range(len(pubkeys)):

        nodeinfo = lnd.get_nodeinfo(pubkeys[i])
        for chan in nodeinfo.channels:

            if (chan.channel_id not in my_channels):
                continue
            if(chan.node1_pub == lnd.get_info().identity_pubkey):
                channel = Channel(
                                chan.channel_id,
                                chan.capacity,
                                chan.node1_pub,
                                chan.node1_policy.fee_base_msat,
                                chan.node1_policy.fee_rate_milli_msat,
                                chan.node2_pub,
                                nodeinfo.node.alias,
                                chan.node2_policy.fee_base_msat,
                                chan.node2_policy.fee_rate_milli_msat,
                )
                s.add(channel)
            elif(chan.node2_pub == lnd.get_info().identity_pubkey):
                channel = Channel(
                                chan.channel_id,
                                chan.capacity,
                                chan.node2_pub,
                                chan.node2_policy.fee_base_msat,
                                chan.node2_policy.fee_rate_milli_msat,
                                chan.node1_pub,
                                nodeinfo.node.alias,
                                chan.node1_policy.fee_base_msat,
                                chan.node1_policy.fee_rate_milli_msat,
                )
                s.add(channel)
    s.commit()

def batch():
    lnd = Lnd()
    if not lnd.valid:
        debug("Could not connect to gRPC endpoint")
        sys.exit(1)

    db_filename = 'sqlite:///' + os.path.join('./graph.db')
    engine = create_engine(db_filename, echo=True)
    Base.metadata.create_all(engine)
    getInfo(engine, lnd)
    getChannels(engine, lnd)

if __name__ == "__main__":
    lnd = Lnd()
    if not lnd.valid:
        debug("Could not connect to gRPC endpoint")
        sys.exit(1)

    db_filename = 'sqlite:///' + os.path.join('./graph.db')
    engine = create_engine(db_filename, echo=True)
    Base.metadata.create_all(engine)
    
    getInfo(engine, lnd)
    getChannels(engine, lnd)