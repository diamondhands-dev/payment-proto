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

from os.path import join, dirname
from dotenv import load_dotenv
load_dotenv(verbose=True)
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

DEFAULT_PRICE = 150

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

        #amount = os.getenv("PRICE", default=DEFAULT_PRICE)
        amount = 15 
        description = "Peek DH channel_id: " + str(channel_id)

        response = self.lnd.get_invoice(amount, description)
        img = qrcode.make(response.payment_request)
        imgStr = "data:image/jpeg;base64," + self.pil_to_base64(img)

        resCreateInvoice = {
            "bolt11": response.payment_request,
            "qrStr": imgStr,
            "paymentHash": response.r_hash.hex(),
        }

        #セキュリティセションセット
        session[str(channel_id)] = response.r_hash.hex()

        #debug
        print("payment_hash1:" + session[str(channel_id)])

        return resCreateInvoice


    #----------------------------------------------------
    #支払い確認＆ノードバランス取得
    #----------------------------------------------------
    def checkInvoice(self, channel_id="", payment_hash=""):
        debug('checkInvoice...')
        resCheckInvoice = ""

        #セキュリティセションチェック
        #try:
        #    session[str(channel_id)]
        #except:
        #    return "PAYMENT UNMATCH ERROR: Session data does not exist."
    
        #if session[str(channel_id)] != payment_hash:
            #return "PAYMENT UNMATCH ERROR: Payment Hash does not match with session data."
        
        # Validate Input
        if not channel_id:
            return "ERROR: Missing channel_id"
        if not payment_hash:
            return "ERROR: Missing payment_hash"

        try:
            response = self.lnd.get_lookupinvoice(payment_hash)
            lnd_result = response.state
        except:
            lnd_result = "ERROR: No such payment_hash"

        if(lnd_result == 1):
            response2 = self.lnd.get_channels()

            for i in range(len(response2.channels)):
                if(str(response2.channels[i].chan_id) == channel_id):
                    resCheckInvoice = {
                        "payment_status": lnd_result,
                        "lnd_response": lnd_result,
                        "capacity": response2.channels[i].capacity,
                        "localBalance": response2.channels[i].local_balance,
                        "remoteBalance": response2.channels[i].remote_balance,
                    }

                    #debug
                    print("payment_hash:" + payment_hash)

                    #全セション変数クリア
                    #session.pop(str(channel_id), None)

                    #debug
                    #print("payment_hash3:" + payment_hash)
                    return resCheckInvoice

            return "ERROR: channel_id Not Found"

        else:
            resCheckInvoice = {
                    "payment_status": 0,
                    "lnd_response": lnd_result,
                    "capacity": 0,
                    "localBalance": 0,
                    "remoteBalance": 0,
                    }

        return resCheckInvoice
    
    def search(self, keyword):
        channels = self.getChannels()
        if not keyword:
            result = channels
        else:
            result = {}
            j = 0
            for i in range(len(channels)):
                alias = channels[i].node2_alias
                if keyword.lower() in alias.lower():
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
