SHELL=/bin/sh -o pipefail

unit_tests := $(shell find unit-tests/ -mindepth 1 -maxdepth 1 -type d -printf '%P\n')
unit_logs := $(patsubst %,log/unit-tests/%,$(unit_tests))
base_pack := "{basename}"
out_pack := "{outname}"
language := "{language}"

compile: pack

log:
	mkdir -p "$@"

basepack: | log
	gh \
		tailor download \
		--outdir "$@" \
		"$(base_pack)" \
	| \
	tee log/download

download: basepack

pack: basepack customize
	rm -rf stage "$@"
	cp -r basepack stage
	./customize | tee log/customize
	gh tailor create -i stage | tee log/create
	mv stage "$@"

log/unit-tests/%: unit-tests/% unit-tests/%/* pack
	mkdir -p log/unit-tests
	gh tailor codeql -- \
		test run \
		--show-extractor-output \
		--additional-packs pack:pack/.codeql/libraries/codeql \
		"unit-tests/$(@F)" | tee "$@".failed
	mv "$@".failed "$@"

inttest.db:
	rm -rf "$@".tmp
	gh \
		tailor make-min-db \
		--language "$(language)" \
		"$@".tmp \
	| \
	tee log/inttest-db
	mv "$@".tmp "$@"

log/integration-tests: pack inttest.db
	gh tailor codeql -- \
		database analyze \
		--threads 0 \
		--additional-packs pack \
		--format csv \
		--output "log/inttest-results.csv" \
		"inttest.db" \
		"$(out_pack)" \
		2>&1 \
	| \
	tee -a "$@".failed
	mv "$@".failed "$@"

unit-test: $(unit_logs)

integration-test: log/integration-tests

test: $(unit_logs) log/integration-tests

publish: $(unit_logs) log/integration-tests
	( \
		( \
			gh tailor \
				autoversion \
				--mode new-on-collision \
				--fail \
				pack \
			&& \
			gh tailor publish pack \
		) \
		|| (test "$$?" = 2 && echo "Nothing left to do") \
	) | tee "log/publish"

.PHONY: clean
clean:
	rm -rf \
		basepack \
		stage \
		pack \
		log \
		inttest.db \
		inttest.db.tmp
