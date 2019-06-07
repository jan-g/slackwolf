build: build-werewolf

build-werewolf: Dockerfile.werewolf
	docker build -t ioctl/werewolf -f Dockerfile.werewolf .

run: run-werewolf

Dockerfile.werewolf: Dockerfile.werewolf.in
	sed -e 's/%%DATE%%/$(shell date +%Y-%m-%d)/g' $< > $@

run-werewolf:
	docker run \
		-d \
		--restart=always \
		--name werewolf \
		-p 127.0.0.1:5002:5002 \
		--env CONFIG=/etc/werewolf/config.yaml \
		--env DATA_DIR=/data \
		-v /var/lib/chatbots/werewolf:/data \
		-v $$(pwd)/config.yaml:/etc/werewolf/config.yaml:ro \
		ioctl/werewolf

stop: stop-werewolf

stop-werewolf:
	-docker rm -f werewolf
