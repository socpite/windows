#!/bin/bash

docker run -it --rm --name windows -p 8006:8006 --device=/dev/kvm --device=/dev/net/tun --cap-add NET_ADMIN -v "${PWD:-.}/src/hud_controller:/hud_controller/src/hud_controller" -v "${PWD:-.}/windows:/storage" --stop-timeout 120 socpite/socpite_windows
