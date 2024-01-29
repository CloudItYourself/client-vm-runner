# worker_manager

export LOOPDEV=$(losetup -f); \
docker run -it \
--env LOOPDEV=${LOOPDEV} \
-v /var/run/docker.sock:/var/run/docker.sock \
-v `pwd`:/workspace:rw \
--privileged \
--device ${LOOPDEV} \
c2vm/builder \
bash buildVM.sh registry.gitlab.com/ronen48/ciy/cloud-iy-vm:latest 2048
