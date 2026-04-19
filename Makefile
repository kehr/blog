BUNDLE ?= bundle
HOST   ?= 127.0.0.1
PORT   ?= 4000

.PHONY: help install serve build prod clean

help:
	@echo "make install   Install gems"
	@echo "make serve     Run dev server with livereload (http://$(HOST):$(PORT))"
	@echo "make build     Build site to _site/"
	@echo "make prod      Build site with JEKYLL_ENV=production"
	@echo "make clean     Remove _site/ and .jekyll-cache/"

install:
	$(BUNDLE) install

serve:
	$(BUNDLE) exec jekyll serve -l -H $(HOST) -P $(PORT)

build:
	$(BUNDLE) exec jekyll build

prod:
	JEKYLL_ENV=production $(BUNDLE) exec jekyll build

clean:
	rm -rf _site .jekyll-cache
