import os
from os.path import join, dirname

from helper import Helper 

helper = Helper()

import flask
from flask import render_template, request, send_from_directory
from flask import Flask, session
from flask_cors import CORS
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import uuid
from datetime import timedelta, datetime

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
Base = declarative_base()
import channel


app = flask.Flask(__name__, static_folder='static')
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)
Session(app)
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["2000 per day", "20 per minute"]
)
CORS(app)

@app.route('/')
def home():
    return render_template("index.html")


#デフォルト情報１取得
@app.route('/self')
def req_self():
    print('requesting my node info ...')

    db_filename = 'sqlite:///' + os.path.join('./graph.db')

    engine = create_engine(db_filename, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker()
    Session.configure(bind=engine)
    s = Session()
    info = s.query(channel.Info).all()

    output = {
        "alias": info[0].alias,
        "publicKey": info[0].identity_pubkey,
    }

    s.close()
    return output


#デフォルト情報２取得
@app.route('/channels')
def req_channels():
    print('requesting channels...')

    db_filename = 'sqlite:///' + os.path.join('./graph.db')

    engine = create_engine(db_filename, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker()
    Session.configure(bind=engine)
    s = Session()
    channels = s.query(channel.Channel).all()
    
    output = {}
    for i in range(len(channels)):
        output[i] = {
            "channelId": str(channels[i].channel_id),
            "alias": channels[i].node2_alias,
            "capacity": channels[i].capacity,
            #"remotePubKey": channels[i].node2_pub,
            #"node1PubKey": channels[i].node1_pub,
            "node1BaseFee": channels[i].node1_base_fee,
            "node1FeeRate": channels[i].node1_fee_rate,
            "node2PubKey": channels[i].node2_pub,
            "node2BaseFee": channels[i].node2_base_fee,
            "node2FeeRate": channels[i].node2_fee_rate,
        }
    s.close()
    return output 



#インボイス発行
@app.route('/invoice/<channel_id>')
def req_invoice(channel_id):
    return helper.createInvoice(channel_id)


#支払いチェック＆バランス情報取得
@app.route('/checkInvoice')
@limiter.limit("20 per minute")
def req_checkInvoice():
    return helper.checkInvoice()


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/img'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.errorhandler(Exception)
def server_error(err):
    print(err)
    return "Some general exception", 500

from apscheduler.schedulers.background import BackgroundScheduler
sched = BackgroundScheduler(daemon=True)
sched.add_job(channel.main,'interval',hours=24) #next_run_time=datetime.now()
sched.start()

if __name__ == '__main__':
    app.config['SECRET_KEY'] = os.getenv(
        "REQUEST_INVOICE_SECRET",
        default=uuid.uuid4())
    app.debug = True
    app.run(host='0.0.0.0', port=8810)