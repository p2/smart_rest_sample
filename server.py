#!/usr/bin/python
#
#  Run locally


import wsgi

import wsgi

if wsgi.DEBUG:
	wsgi.app.run(host='0.0.0.0', port=8008, reloader=True)
else:
	wsgi.app.run(host='0.0.0.0', port=8008)
