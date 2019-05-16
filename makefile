help:
	./cmd.sh -h
install:
	./cmd.sh install
test:
	./cmd.sh test
clean:
	./cmd.sh clean
update_authors:
	git log --pretty="%an %ae%n%cn %ce" | sort | uniq | grep -v 'noreply@github.com' > AUTHORS
