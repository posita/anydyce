all : \
	../docs/anydice-playground.svg \
	../docs/index.md \
	../docs/license.md \
	../requirements-dev.txt \
	jupyterlite \
	playground

.PHONY : all jupyterlite playground wheel FORCE
FORCE :

wheel : FORCE
	cd .. && uv build --wheel

../requirements-dev.txt : Makefile ../uv.lock
	cd .. && uv export --format requirements-txt --locked --no-hashes --output-file "$$( basename $@ )"

../docs/anydice-playground.svg : Makefile
	curl --fail --silent --show-error --location --output $@ 'https://img.shields.io/badge/%F0%9F%A4%B7%F0%9F%8E%B2%20AnyDice-Compatible%20%F0%9F%9B%9D-teal.svg'

../docs/index.md : ../README.md FORCE
	@set -eu; \
	raw_version=$$("$${PYTHON:-python3}" -c 'import importlib.metadata; print(importlib.metadata.version("dyceum"))'); \
	case "$$raw_version" in \
		*+*|*.dev*) git_ref=main; docs_version=latest; release=;; \
		*) git_ref="v$$raw_version"; docs_version=$$(printf '%s' "$$raw_version" | cut -d. -f1,2); release=1;; \
	esac; \
	temp_file=$$(mktemp ../docs/.index.md.XXXXXX); \
	trap 'rm -f "$$temp_file" "$$temp_file.release"' 0; \
	sed \
		-e '/<!-- docs:hide:start -->/,/<!-- docs:hide:end -->/d' \
		-e "s#raw.githubusercontent.com/posita/dyceum/main/#raw.githubusercontent.com/posita/dyceum/$$git_ref/#g" \
		-e "s#github.com/posita/dyceum/blob/main/#github.com/posita/dyceum/blob/$$git_ref/#g" \
		-e "s#github.com/posita/dyceum/tree/main/#github.com/posita/dyceum/tree/$$git_ref/#g" \
		-e "s#https://dyceum.org/latest/#https://dyceum.org/$$docs_version/#g" \
		../README.md > "$$temp_file"; \
	if [ -n "$$release" ]; then \
		sed -E \
			-e "s#(https://img\.shields\.io/pypi/[^/]+/dyceum)\.svg#\1/$$raw_version.svg#g" \
			-e "s#(https://pypi\.org/project/dyceum/)\)#\1$$raw_version/)#g" \
			"$$temp_file" > "$$temp_file.release"; \
		mv "$$temp_file.release" "$$temp_file"; \
	fi; \
	if ! cmp -s "$$temp_file" "$@"; then \
		chmod 644 "$$temp_file"; \
		mv "$$temp_file" "$@"; \
	fi

../docs/license.md : ../LICENSE
	cp $< $@

../docs/notebooks/%.ipynb : nb_%.py
	jupytext --to notebook --update $< --output $@
	ruff check --fix $@
	ruff format $@
	touch $@

# Prints the pinned "none-any" wheel URL for each package named on the
# command line.
UV_LOCK_WHEELS = "$${PYTHON:-python3}" -c 'import sys, tomllib; packages = tomllib.load(open("uv.lock", "rb"))["package"]; print("\n".join(next(w["url"] for p in packages if p["name"] == pkg_name for w in p.get("wheels", []) if "none-any" in w["url"]) for pkg_name in sys.argv[1:]))'

jupyterlite : FORCE wheel ../docs/notebooks/dyceum_intro.ipynb
	@cd .. && set -eu; \
		dyceum_wheel=$$(ls -t dist/dyceum*-none-any.whl | head -n 1); \
		test -f "$$dyceum_wheel"; \
		set -- --piplite-wheels "$$dyceum_wheel"; \
		for url in $$($(UV_LOCK_WHEELS) dyce lark optype ipywidgets jupyterlab-widgets widgetsnbextension); do \
			set -- "$$@" --piplite-wheels "$$url"; \
		done; \
		jupyter lite build --debug --output-dir docs/jupyter "$$@"

playground : FORCE wheel
	@cd .. && set -eu; \
		rm -rf docs/playground; \
		rsync -a \
			--exclude node_modules \
			--exclude package.json \
			--exclude test \
			playground/ docs/playground/; \
		wheels_dir=docs/playground/wheels; \
		mkdir -p "$$wheels_dir"; \
		dyceum_wheel=$$(ls -t dist/dyceum*-none-any.whl | head -n 1); \
		test -f "$$dyceum_wheel"; \
		cp "$$dyceum_wheel" "$$wheels_dir"; \
		names=$$(basename "$$dyceum_wheel"); \
		for url in $$($(UV_LOCK_WHEELS) dyce lark optype); do \
			curl --fail --silent --show-error --location \
				--output "$$wheels_dir/$$(basename "$$url")" "$$url"; \
			names="$$names $$(basename "$$url")"; \
		done; \
		{ printf '[\n'; \
			first=1; \
			for name in $$names; do \
				if [ "$$first" = 1 ]; then first=0; else printf ',\n'; fi; \
				printf '  "%s"' "$$name"; \
			done; \
			printf '\n]\n'; \
		} > "$$wheels_dir/index.json"
