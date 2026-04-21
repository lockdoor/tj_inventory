NAME = django

build:
	docker build -t $(NAME) .

run:
	docker run -it --rm -p 8000:8000 \
	--name $(NAME) \
	-e DJANGO_SECRET_KEY="$$(cat ../secrets/django_secret_key.txt)" \
	-v $(PWD)/srcs/media:/app/media \
	-v $(PWD)/srcs/db.sqlite3:/app/db.sqlite3 \
	$(NAME)

exec:
	docker exec -it $(NAME) bash

stop:
	docker stop $(NAME)

rm:
	docker rm $(NAME)