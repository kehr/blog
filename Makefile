BUNDLE ?= bundle
PYTHON ?= python3
HOST   ?= 127.0.0.1
PORT   ?= 4000

.PHONY: help install serve serve-drafts build prod check lint lint-inline-scripts new publish publish-list publish-check test-publish clean

help:
	@echo "make install            Install gems"
	@echo "make serve              Dev server with livereload (http://$(HOST):$(PORT))"
	@echo "make serve-drafts       Dev server including _drafts/"
	@echo "make build              Build site to _site/"
	@echo "make prod               Build site with JEKYLL_ENV=production"
	@echo "make check              Production build + htmlproofer (internal links)"
	@echo "make lint               Run all template lints"
	@echo "make lint-inline-scripts  Block '//' line comments inside inline <script> blocks"
	@echo "make new title=...      Create a new draft in _drafts/ (optional: slug=...)"
	@echo "make publish file=... slug=...  Publish draft to _posts/ with full pipeline"
	@echo "make publish-list       List all drafts in _drafts/"
	@echo "make publish-check file=... slug=...  Dry-run publish (no disk writes)"
	@echo "make test-publish       Run publish pipeline test suite"
	@echo "make clean              Remove _site/ and .jekyll-cache/"

install:
	$(BUNDLE) install

serve:
	$(BUNDLE) exec jekyll serve -l -H $(HOST) -P $(PORT)

serve-drafts:
	$(BUNDLE) exec jekyll serve -l --drafts -H $(HOST) -P $(PORT)

build:
	$(BUNDLE) exec jekyll build

prod:
	JEKYLL_ENV=production $(BUNDLE) exec jekyll build

check: prod
	$(BUNDLE) exec htmlproofer _site \
	  --disable-external \
	  --allow-hash-href \
	  --ignore-urls "/^\/(posts|tags|categories|archives)\//"

lint: lint-inline-scripts

lint-inline-scripts:
	@$(PYTHON) scripts/lint-inline-scripts.py

new:
	@if [ -z "$(title)" ]; then \
	  echo "usage: make new title=\"Post Title\" [slug=my-slug]"; exit 1; \
	fi
	@scripts/new-post.sh "$(title)" $(slug)

publish:
	@if [ -z "$(file)" ] || [ -z "$(slug)" ]; then \
	  echo 'usage: make publish file="..." slug="..." [categories=...] [tags=...] [image=...] [description=...] [date=...] [src=...] [dry-run=1] [force=1]'; exit 1; \
	fi
	@$(PYTHON) scripts/publish.py \
	  --file "$(file)" --slug "$(slug)" \
	  $(if $(categories),--categories "$(categories)") \
	  $(if $(tags),--tags "$(tags)") \
	  $(if $(image),--image "$(image)") \
	  $(if $(description),--description "$(description)") \
	  $(if $(date),--date "$(date)") \
	  $(if $(src),--src "$(src)") \
	  $(if $(dry-run),--dry-run) \
	  $(if $(force),--force)

publish-list:
	@$(PYTHON) scripts/publish.py --list

publish-check:
	@if [ -z "$(file)" ] || [ -z "$(slug)" ]; then \
	  echo 'usage: make publish-check file="..." slug="..."'; exit 1; \
	fi
	@$(PYTHON) scripts/publish.py \
	  --file "$(file)" --slug "$(slug)" --dry-run \
	  $(if $(categories),--categories "$(categories)") \
	  $(if $(tags),--tags "$(tags)") \
	  $(if $(image),--image "$(image)") \
	  $(if $(description),--description "$(description)") \
	  $(if $(src),--src "$(src)")

test-publish:
	@$(PYTHON) -m pytest scripts/test_publish.py -v

clean:
	rm -rf _site .jekyll-cache
