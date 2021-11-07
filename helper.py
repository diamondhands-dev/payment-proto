from lnd import Lnd
import sys

import os
from os.path import join, dirname
from flask import session
import base64
import qrcode
from io import BytesIO
from PIL import Image

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
