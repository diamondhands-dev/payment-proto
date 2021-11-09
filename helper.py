from lnd import Lnd
import sys

import os
from os.path import join, dirname
from flask import session
import base64
import qrcode
from io import BytesIO
from PIL import Image

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
Base = declarative_base()
import channel

def debug(message):
    sys.stderr.write(message + "\n")

class Helper:
    lnd = Lnd()
    if not lnd.valid:
        debug("Could not connect to gRPC endpoint")
        sys.exit(1)

    def pil_to_base64(self, img):
        buffer = BytesIO()
        img.save(buffer, format="jpeg")
        img_str = base64.b64encode(buffer.getvalue()).decode("ascii")

        return img_str

    def getInfo(self):
        db_filename = 'sqlite:///' + os.path.join('./graph.db')

        engine = create_engine(db_filename, echo=True)
        Base.metadata.create_all(engine)

        Session = sessionmaker()
        Session.configure(bind=engine)
        s = Session()
        info = s.query(channel.Info).all()
        s.close()

        return info

    def getChannels(self):
        db_filename = 'sqlite:///' + os.path.join('./graph.db')

        engine = create_engine(db_filename, echo=True)
        Base.metadata.create_all(engine)

        Session = sessionmaker()
        Session.configure(bind=engine)
        s = Session()
        channels = s.query(channel.Channel).all()
        s.close()

        return channels

    #----------------------------------------------------
    #インボイス発行
    #----------------------------------------------------
    def createInvoice(self, channel_id):

        #channel_idセションセット
        session["channel_id"] = channel_id

        amount = 150
        description = "Peek DH channel_id: " + str(channel_id)

        response = self.lnd.get_invoice(amount, description)
        img = qrcode.make(response.payment_request)
        imgStr = "data:image/jpeg;base64," + self.pil_to_base64(img)

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
    def checkInvoice(self):
        debug('checkInvoice...')

        response = self.lnd.get_lookupinvoice(session["payment_hash"])

        if(response.state == 1):

            response2 = self.lnd.get_channels()

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
    
    def search(self, keyword):
        channels = self.getChannels()
        if not keyword:
            result = channels
        else:
            result = {}
            j = 0
            for i in range(len(channels)):
                alias = channels[i].node2_alias
                if keyword in alias:
                    result[j] = channels[i]
                    j += 1

        output = self.convertChannelsToOutput(result)
        #output[-1] = {"keyword":keyword}
        return output

    def convertChannelsToOutput(self, channels):
        output = {}
        for i in range(len(channels)):
            output[i] = {
                "channelId": str(channels[i].channel_id),
                "alias": channels[i].node2_alias,
                "capacity": channels[i].capacity,
                "node1BaseFee": channels[i].node1_base_fee,
                "node1FeeRate": channels[i].node1_fee_rate,
                "node2PubKey": channels[i].node2_pub,
                "node2BaseFee": channels[i].node2_base_fee,
                "node2FeeRate": channels[i].node2_fee_rate,
            }
        return output
