from lnd import Lnd
import sys

import os
from os.path import join, dirname
import base64
import qrcode
from io import BytesIO
from PIL import Image

from sqlalchemy import create_engine
from sqlalchemy import or_
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
INVOICE_MEMO_PREFIX = "DH Channel Explorer for channel_id: "
DEFAULT_CHANNELCOUNT = 10

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

    def getChannels(self, keyword=None, channelCount=None, page=None):
        db_filename = 'sqlite:///' + os.path.join('./graph.db')

        engine = create_engine(db_filename, echo=True)
        Base.metadata.create_all(engine)

        Session = sessionmaker()
        Session.configure(bind=engine)
        s = Session()
        q = s.query(channel.Channel).order_by(channel.Channel.channel_id)
        if keyword:
            q = q.filter(or_(channel.Channel.node2_alias.ilike(f"%{keyword}%"), channel.Channel.node2_pub == keyword))
        if channelCount and page:
            page = page - 1
            sliceStart = channelCount * page
            sliceEnd = sliceStart + channelCount
            q = q.slice(sliceStart, sliceEnd)
        channels = q.all()
        s.close()

        return channels

    def getChannelTotalCount(self):
        db_filename = 'sqlite:///' + os.path.join('./graph.db')

        engine = create_engine(db_filename, echo=True)
        Base.metadata.create_all(engine)

        Session = sessionmaker()
        Session.configure(bind=engine)
        s = Session()
        count = s.query(channel.Channel).count()
        s.close()

        return count

    #----------------------------------------------------
    #インボイス発行
    #----------------------------------------------------
    def createInvoice(self, channel_id):

        try:
            amount = int(os.getenv("PRICE", default=DEFAULT_PRICE))
        except:
            return "ERROR: Could not set Amount"

        description = INVOICE_MEMO_PREFIX + str(channel_id)

        response = self.lnd.get_invoice(amount, description)
        img = qrcode.make(response.payment_request)
        imgStr = "data:image/jpeg;base64," + self.pil_to_base64(img)

        resCreateInvoice = {
            "bolt11": response.payment_request,
            "qrStr": imgStr,
            "paymentHash": response.r_hash.hex(),
            "amount": amount,
            "description": description,
        }

        #debug
        print("payment_hash: " + response.r_hash.hex())
        print("amount: " + str(amount))
        print("description: " + description)

        return resCreateInvoice


    #----------------------------------------------------
    #支払い確認＆ノードバランス取得
    #----------------------------------------------------
    def checkInvoice(self, payment_hash=""):
        debug('checkInvoice...')
        resCheckInvoice = ""

        # Validate Input
        if not payment_hash:
            return "ERROR: Missing payment_hash"

        try:
            response = self.lnd.get_lookupinvoice(payment_hash)
            lnd_result = response.state
            channel_id = response.memo[len(INVOICE_MEMO_PREFIX):]
            debug("Invoice Memo: " + response.memo)
            debug("Channel_id: " + channel_id)
        except:
            lnd_result = "ERROR: No such payment_hash"
            debug(lnd_result)

        if(lnd_result == 1):
            response2 = self.lnd.get_channels()

            for i in range(len(response2.channels)):
                if(str(response2.channels[i].chan_id) == channel_id):
                    resCheckInvoice = {
                        "paymentStatus": lnd_result,
                        "lndResponse": lnd_result,
                        "capacity": response2.channels[i].capacity,
                        "localBalance": response2.channels[i].local_balance,
                        "remoteBalance": response2.channels[i].remote_balance,
                    }

                    #debug
                    debug("Payment Status: Paid")
                    debug("payment_hash:" + payment_hash)

                    return resCheckInvoice

            resCheckInvoice = "ERROR: channel_id Not Found"
            #debug
            debug(resCheckInvoice)
            return resCheckInvoice

        else:
            resCheckInvoice = {
                    "paymentStatus": 0,
                    "lndResponse": lnd_result,
                    }
            #debug
            debug("Payment Status: Not Paid")

        return resCheckInvoice
    
    def search(self, keyword=None, channelCount=None, page=None):

        if channelCount or page:
            if channelCount:
                try:
                    channelCount = int(channelCount)
                    if channelCount < 1: raise
                except:
                    channelCount = DEFAULT_CHANNELCOUNT
            else:
                channelCount = DEFAULT_CHANNELCOUNT
        
            if page:
                try:
                    page = int(page)
                    if page < 1: raise
                except:
                    page = 1
            else:
                page = 1

        channels = self.getChannels(keyword, channelCount, page)
        channelTotal = self.getChannelTotalCount()
        output = {}
        channelsArray = []

        for c in channels:
            channelsArray.append({
                "channelId": str(c.channel_id),
                "alias": c.node2_alias,
                "capacity": c.capacity,
                "node1BaseFee": c.node1_base_fee,
                "node1FeeRate": c.node1_fee_rate,
                "node2PubKey": c.node2_pub,
                "node2BaseFee": c.node2_base_fee,
                "node2FeeRate": c.node2_fee_rate,
                })
        
        output = {
            "channelCount": channelCount,
            "channels": channelsArray,
            "page": page,
            "channelTotal": channelTotal,
            }
        return output
