build:
	run-rstblog build

serve:
	run-rstblog serve

upload:
	scp -r _build/* flow.srv.pocoo.org:/srv/websites/werkzeug.pocoo.org/static
