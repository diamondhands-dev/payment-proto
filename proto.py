import os
from os.path import join, dirname
from helper import Helper 
import flask
from flask import render_template, request, send_from_directory
from flask import Flask, session
from flask_cors import CORS
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import uuid
from datetime import timedelta, datetime
import channel

from os.path import join, dirname
from dotenv import load_dotenv
load_dotenv(verbose=True)
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

helper = Helper()
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

# デフォルトトップページ
# Get default top page
@app.route('/')
def home():
    return render_template("index.html")

# 自ノード情報取得
# Get self node info
@app.route('/self')
def req_self():
    print('requesting my node info ...')

    info = helper.getInfo()
    channels = helper.getChannels()

    capacitySum = 0
    channelCount = len(channels)
    for i in range(channelCount):
        capacitySum += channels[i].capacity

    output = {
        "alias": info[0].alias,
        "publicKey": info[0].identity_pubkey,
        "channelCount": channelCount,
        "capacitySum": capacitySum,
    }

    return output

# 全チャネル情報取得
# Get all channels info
@app.route('/channels')
def req_channels():
    print('requesting channels...')

#    channels = helper.getChannels()
#    output = helper.convertChannelsToOutput(channels)
#    return output
    return helper.search()

# 検索機能
# Search Functionality
@app.route('/search')
@app.route('/search/')
#def req_search_blank():
    # Parameter Missing
#    return helper.search('')
@app.route('/search/<keyword>')
def req_search(keyword=None):
    channelCount = request.args.get('channelCount')
    page = request.args.get('page')
    return helper.search(keyword, channelCount, page)

# インボイス発行
# Issue invoice
@app.route('/invoice')
@app.route('/invoice/')
def req_invoice_blank():
    # Parameter Missing
    return '{}'

@app.route('/invoice/<channel_id>')
def req_invoice(channel_id):
    return helper.createInvoice(channel_id)


#支払いチェック＆バランス情報取得
# Check if invoice paid & get channel balance info
@app.route('/checkInvoice')
@app.route('/checkInvoice/')
@app.route('/checkInvoice/<payment_hash>')
@limiter.limit("20 per minute")
def req_checkInvoice(payment_hash=""):
    return helper.checkInvoice(payment_hash)

# その他
# Others
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/img'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.errorhandler(Exception)
def server_error(err):
    print(err)
    return "Some general exception", 500

# バッチスケジュール実行
# Set batch schedule
from apscheduler.schedulers.background import BackgroundScheduler
sched = BackgroundScheduler(daemon=True)
sched.add_job(channel.main,'interval',hours=24) #next_run_time=datetime.now()
sched.start()

# メイン実行
# Main
if __name__ == '__main__':
    port_number = os.getenv("FLASK_PORT_NUMBER", default=8810)
    crt_file = os.getenv("FLASK_SSL_CERTFILE", default=None)
    key_file = os.getenv("FLASK_SSL_KEYFILE", default=None)

    app.config['SECRET_KEY'] = os.getenv(
        "REQUEST_INVOICE_SECRET",
        default=uuid.uuid4())
    app.debug = True
    
    if crt_file and key_file:
        context = (crt_file, key_file)
        app.run(host='0.0.0.0', port=port_number, ssl_context=context)
    else:
        app.run(host='0.0.0.0', port=port_number)

