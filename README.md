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
LND_GRPC_ENDPOINT=192.168.0.1
LND_GRPC_PORT=10009
LND_GRPC_CERT="path_to_tls.cert"
LND_GRPC_MACAROON="path_to_readonly.macaroon"
LND_GRPC_MACAROON_INVOICE="path_to_invoice.macaroon"
```

### Running
```
$ python3 proto.py
```

Go to http://localhost:8810

You may want to run a command below to update database manually.
```
$ python3 channel.py
```


### Onion routing
TBA


### Docker
TBA

### Python gRPC
This tool uses a Python gRPC to communicate with lnd. Follow the instruction below.

https://github.com/lightningnetwork/lnd/blob/master/docs/grpc/python.md
