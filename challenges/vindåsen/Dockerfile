FROM ubuntu:26.04

# dosbox-x is in the universe component; enable it for both source formats
# (DEB822 used in 22.04+, legacy sources.list kept for completeness).
RUN (test -f /etc/apt/sources.list.d/ubuntu.sources \
     && sed -i '/^Components:/ s/$/ universe/' /etc/apt/sources.list.d/ubuntu.sources \
     || sed -i 's/ main$/ main universe/g' /etc/apt/sources.list) \
 && apt-get update \
 && apt-get install -y --no-install-recommends tini dosbox-x socat python3-minimal \
 && rm -rf /var/lib/apt/lists/*

# Windows 1.01 system files (shared by both VMs)
COPY WIN1.01/ /challenge/WIN1.01/

# VINDAASEN runtime: app EXE, data files, and C: overlay (WIN.INI auto-launch)
COPY VINDAASEN/VINDÅSEN.EXE \
     VINDAASEN/VARER.TXT \
     VINDAASEN/VINDÅSEN.INI \
     /challenge/VINDAASEN/
COPY VINDAASEN/WINOVL/ /challenge/VINDAASEN/WINOVL/

# VDLEV runtime: monitor + service EXEs, flag, and C: overlay (WIN.INI auto-launch)
COPY VDLEV/VDLOVV.EXE \
     VDLEV/VDLEV.EXE \
     VDLEV/FLAG.TXT \
     /challenge/VDLEV/
COPY VDLEV/WINOVL/ /challenge/VDLEV/WINOVL/

COPY launch.sh /challenge/launch.sh
COPY control.sh /challenge/control.sh
COPY broker.py /challenge/broker.py
RUN chmod +x /challenge/launch.sh /challenge/control.sh /challenge/broker.py

# BBS ordering line (broker.py front-end; COM2 itself is loopback-only on 12323)
EXPOSE 2323
# Control channel
EXPOSE 1986

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/challenge/launch.sh"]
