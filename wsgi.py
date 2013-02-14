# good morning!

import bottle
import json
from jinja2 import Template, Environment, PackageLoader

from tokenstore import TokenStore
from smart_client_python.client import SMARTClient

from settings import ENDPOINTS


# bottle and Jinja setup
app = bottle.Bottle()
application = app				# needed for AppFog			
_jinja = Environment(loader=PackageLoader('wsgi', 'templates'), trim_blocks=True)
_smart = None
DEBUG = True


def _serve_static(file, root):
	""" Serves a static file or a 404 """
	try:
		return bottle.static_file(file, root=root)
	except Exception, e:
		bottle.abort(404)


def _smart_client(api_base, record_id=None):
	""" Returns the SMART client, configured accordingly """
	global _smart
	if _smart is None or _smart.api_base != api_base:
		server = ENDPOINTS.get(api_base)
		if server is None:
			_log_error("There is no server with base URI %s" % api_base)
			bottle.abort(404)
			return None
		
		# instantiate
		app_id = server.get('app_id')
		_smart = SMARTClient(app_id, api_base, server)
	
	_smart.record_id = record_id
	return _smart


def _log_debug(log):
	if DEBUG:
		print log

def _log_error(err):
	print err
		


# ------------------------------------------------------------------------------ Token Handling
def _test_record_token(api_base, record_id, token):
	""" Tries to fetch demographics with the given token and returns a bool whether thas was successful """
	
	smart = _smart_client(api_base, record_id)
	smart.update_token(token)
	try:
		demo = smart.get_demographics()
		if '200' == demo.response.get('status'):
			return True
	except Exception, e:
		pass
	
	return False


def _request_token_for_record_if_needed(api_base, record_id):
	""" Requests a request token for record id, if needed """
	ts = TokenStore()
	token = ts.tokenForRecord(api_base, record_id)
	
	# we already got a token, test if it still works
	if token is not None and _test_record_token(api_base, record_id, token):
		_log_debug("reusing existing token")
		return False, None
	
	# request a token
	_log_debug("requesting token for record %s on %s" % (record_id, api_base))
	smart = _smart_client(api_base, record_id)
	smart.token = None
	try:
		token = smart.fetch_request_token()
	except Exception, e:
		return False, str(e)
	
	# got a token, store it
	if token is not None and not ts.storeTokenForRecord(api_base, record_id, token):
		return False, "Failed to store request token"
	
	# now go and authorize the token
	_log_debug("redirecting to authorize token")
	bottle.redirect(smart.auth_redirect_url)
	return True, None


def _exchange_token(req_token, verifier):
	""" Takes the request token and the verifier, obtained in our authorize callback, and exchanges it for an access
	token. Stores the access token and returns api_base and record_id as tuple. """
	ts = TokenStore()
	full_token, api_base, record_id = ts.tokenServerRecordForToken(req_token)
	if record_id is None:
		_log_error("Unknown token, cannot exchange %s" % req_token)
		return None, None
	
	# exchange the token
	_log_debug("exchange token: %s" % full_token)
	smart = _smart_client(api_base, record_id)
	smart.update_token(full_token)
	try:
		acc_token = smart.exchange_token(verifier)
	except Exception, e:
		_log_error("token exchange failed: %s" % e)
		return api_base, None
	
	# success, store it
	_log_debug("did exchange token: %s" % acc_token)
	ts.storeTokenForRecord(api_base, record_id, acc_token)
	smart.update_token(acc_token)
	
	return api_base, record_id


# ------------------------------------------------------------------------------ Index
@app.get('/')
@app.get('/index.html')
def index():
	""" The index page makes sure we select a patient and we have a token """
	api_base = bottle.request.query.get('api_base')
	record_id = bottle.request.query.get('record_id')
	
	# no endpoint, show selector
	if api_base is None:
		bottle.redirect('endpoint_select')
		return
	
	smart = _smart_client(api_base, record_id)
	
	# no record id, call launch page
	if record_id is None:
		launch = smart.launch_url
		if launch is None:
			return "Unknown app start URL, cannot launch without a record id"
		
		bottle.redirect(launch)
		return
	
	# do we have a token?
	did_fetch, error_msg = _request_token_for_record_if_needed(api_base, record_id)
	if did_fetch:
		return		# the call above will redirect if true anyway, but let's be sure to exit here
	if error_msg:
		return error_msg
	
	# ok, let's fetch demographics and display the name
	# NOTE: we fetched the demographics above to test the token, maybe cache that result somewhere?
	demo = smart.get_demographics()
	sparql = """
		PREFIX vc: <http://www.w3.org/2006/vcard/ns#>
		SELECT ?given ?family
		WHERE {
			[] vc:n ?vcard .
			OPTIONAL { ?vcard vc:given-name ?given . }
			OPTIONAL { ?vcard vc:family-name ?family . }
		}
	"""
	results = demo.graph.query(sparql)
	record_name = 'Unknown'
	if len(results) > 0:
		res = list(results)[0]
		record_name = '%s %s' % (res[0], res[1])
	
	# render index
	template = _jinja.get_template('index.html')
	return template.render(api_base=api_base, record_id=record_id, record_name=record_name)


@app.get('/endpoint_select')
def endpoint():
	""" Shows all possible endpoints, sending the user back to index when one is chosen """
	
	# get the callback
	# NOTE: this is done very cheaply, we need to make sure to end the callback url with either "?" or "&"
	callback = bottle.request.query.get('callback', 'index.html?')
	if '?' != callback[-1] and '&' != callback[-1]:
		callback += '&' if '?' in callback else '?'
	
	available = []
	for api_base, srvr in ENDPOINTS.iteritems():
		available.append({
			"name": srvr.get('name', 'Unnamed'),
			"url": api_base
		})
	
	# render selections
	template = _jinja.get_template('endpoint_select.html')
	return template.render(endpoints=available, callback=callback)
	


# ------------------------------------------------------------------------------ Authorization
@app.get('/authorize')
def authorize():
	""" Extract the oauth_verifier and exchange it for an access token """
	req_token = {'oauth_token': bottle.request.query.get('oauth_token')}
	verifier = bottle.request.query.get('oauth_verifier')
	api_base, record_id = _exchange_token(req_token, verifier)
	if record_id is not None:
		bottle.redirect('/index.html?api_base=%s&record_id=%s' % (api_base, record_id))
	
	# no record id
	bottle.abort(400)


# ------------------------------------------------------------------------------ Static requests
@app.get('/static/<filename>')
def static(filename):
	return _serve_static(filename, 'static')
