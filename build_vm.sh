#! /bin/bash

docker login -u u -p glpat-MUekjoxQDubT9QoHyuEx registry.gitlab.com/ronen48/ciy
docker build . -f internal_controller_dockerfile -t registry.gitlab.com/ronen48/ciy/cloud-iy-vm:latest
docker pull linkacloud/d2vm
alias d2vm="docker run --rm -it -v /var/run/docker.sock:/var/run/docker.sock --privileged -v \$PWD:/d2vm -w /d2vm linkacloud/d2vm:latest"
sudo d2vm convert registry.gitlab.com/ronen48/ciy/cloud-iy-vm:latest -p MyP4Ssw0rd
