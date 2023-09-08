FROM ubuntu:22.04
RUN apt update &&  \
    apt upgrade -y && \
    apt install python3-pip -y
ENTRYPOINT ["/bin/bash"]