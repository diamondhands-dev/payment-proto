# Peeking channel info Server

This service allows the LN node operator to sell channel information.

### Installation
```
$ git clone https://github.com/diamondhands-dev/payment-proto.git
$ cd payment-proto
$ pip3 install -r requirements.txt
```

### Configuration
Copy and rename `.env.example` file to `.env`.
```
$ cp .env.example .env
```

Set configuration for your LND as follows.
```
LND_GRPC_ENDPOINT=127.0.0.1
LND_GRPC_PORT=10009
LND_GRPC_CERT="path_to_tls.cert"
LND_GRPC_MACAROON="path_to_readonly.macaroon"
LND_GRPC_MACAROON_INVOICE="path_to_invoice.macaroon"
FLASK_PORT_NUMBER=8810
FLASK_SSL_CERTFILE="path_to_certificate.crt"
FLASK_SSL_KEYFILE="path_to_private.key"
PRICE=price_per_channel_in_sats_default_is_150
```

### Running
Run the database creation/update program at least once before you run proto.py for the first time
```
$ python3 channel.py
$ python3 proto.py
```

or to run in the background
```
$ nohup python3 proto.py &
```

If you have set FLASK_SSL_CERTFILE and FLASK_SSL_KEYFILE then go to https://localhost:8810
If not, go to http://localhost:8810

If the channel info seems incorrect, you may want to run the command below to update the database manually.
```
$ python3 channel.py
```


### Onion routing
TBA


### Docker
TBA

### Python gRPC
This tool uses the Python gRPC to communicate with lnd. Follow the instruction below.

https://github.com/lightningnetwork/lnd/blob/master/docs/grpc/python.md
