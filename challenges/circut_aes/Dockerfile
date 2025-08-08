FROM debian:trixie
RUN apt-get update -qy && DEBIAN_FRONTEND=noninteractive apt-get install -qy python3 python3-pycryptodome socat
COPY challenge.py flag /challenge/
WORKDIR /challenge
CMD socat tcp-listen:1337,reuseaddr,fork system:./challenge.py
