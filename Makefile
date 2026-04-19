BUNDLE ?= bundle
HOST   ?= 127.0.0.1
PORT   ?= 4000

.PHONY: help install serve serve-drafts build prod check new publish clean

help:
	@echo "make install        Install gems"
	@echo "make serve          Dev server with livereload (http://$(HOST):$(PORT))"
	@echo "make serve-drafts   Dev server including _drafts/"
	@echo "make build          Build site to _site/"
	@echo "make prod           Build site with JEKYLL_ENV=production"
	@echo "make check          Production build + htmlproofer (internal links)"
	@echo "make new title=...  Create a new draft in _drafts/ (optional: slug=...)"
	@echo "make publish slug=x Move _drafts/<slug>.md to _posts/YYYY-MM-DD-<slug>.md"
	@echo "make clean          Remove _site/ and .jekyll-cache/"

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

new:
	@if [ -z "$(title)" ]; then \
	  echo "usage: make new title=\"Post Title\" [slug=my-slug]"; exit 1; \
	fi
	@scripts/new-post.sh "$(title)" $(slug)

publish:
	@if [ -z "$(slug)" ]; then \
	  echo "usage: make publish slug=my-slug"; exit 1; \
	fi
	@scripts/publish-post.sh "$(slug)"

clean:
	rm -rf _site .jekyll-cache
