# good morning!

import flask
import json
import logging
import tokenstore
import settings
from smart_client_python.client import SMARTClient

# Note: We're using ./app for the template directory and also for
# the static files, but static file URLs start with /static/
application = app = flask.Flask(  # Some PaaS need "application" here
    'wsgi',
    template_folder='app',
    static_folder='app',
    static_url_path='/static'
)

# Debugging and logging configuration
app.debug = True
if app.debug:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.WARNING)


# ------------------------------------------------------ SMARTClient Init
_smart = None  # A global flag to check is the SMARTClient is configured


def _smart_client(api_base, record_id=None):
    """ Returns the SMART client, configured accordingly. """
    global _smart
    if _smart is None or _smart.api_base != api_base:
        server = settings.ENDPOINTS.get(api_base)
        if server is None:
            logging.error("There is no server with base URI %s" % api_base)
            flask.abort(404)
            return None

        # instantiate
        app_id = server.get('app_id')
        _smart = SMARTClient(app_id, api_base, server)

    _smart.record_id = record_id
    return _smart


# ------------------------------------------------------------ Token Handling
def _test_record_token(api_base, record_id, token):
    """ Tries to fetch demographics with the given token and returns a
        bool whether thas was successful. """

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
    """ Requests a request token for record id, if needed. """
    ts = tokenstore.TokenStore()
    token = ts.tokenForRecord(api_base, record_id)

    # we already got a token, test if it still works
    if token is not None and _test_record_token(api_base, record_id, token):
        logging.debug("reusing existing token")
        return False, None

    # request a token
    logging.debug("requesting token for record %s on %s" %
                  (record_id, api_base))
    smart = _smart_client(api_base, record_id)
    smart.token = None
    try:
        token = smart.fetch_request_token()
    except Exception, e:
        return False, str(e)

    # got a token, store it
    if token is not None and not ts.storeTokenForRecord(api_base,
                                                        record_id,
                                                        token):
        return False, "Failed to store request token"

    return True, None


def _exchange_token(req_token, verifier):
    """ Takes the request token and the verifier, obtained in our authorize
        callback, and exchanges it for an access token. Stores the access
        token and returns api_base and record_id as tuple. """
    ts = tokenstore.TokenStore()
    full_token, api_base, record_id = ts.tokenServerRecordForToken(req_token)
    if record_id is None:
        logging.error("Unknown token, cannot exchange %s" % req_token)
        return None, None

    # exchange the token
    logging.debug("exchange token: %s" % full_token)
    smart = _smart_client(api_base, record_id)
    smart.update_token(full_token)
    try:
        acc_token = smart.exchange_token(verifier)
    except Exception, e:
        logging.error("token exchange failed: %s" % e)
        return api_base, None

    # success, store it
    logging.debug("did exchange token: %s" % acc_token)
    ts.storeTokenForRecord(api_base, record_id, acc_token)
    smart.update_token(acc_token)

    return api_base, record_id


# -------------------------------------------------------------------- Index
@app.route('/')
@app.route('/index.html')
def index():
    """ The index page makes sure we select a patient and we have a token. """
    api_base = flask.request.args.get('api_base')
    record_id = flask.request.args.get('record_id')

    # no endpoint, show selector
    if api_base is None:
        return flask.redirect('/endpoint_select')

    smart = _smart_client(api_base, record_id)

    # no record id, call launch page
    if record_id is None:
        launch = smart.launch_url
        if launch is None:
            return "Unknown app start URL, cannot launch without a record id"

        logging.debug('smart.launch_url: ' + launch)
        return flask.redirect(launch)

    # do we have a token?
    did_fetch, error_msg = _request_token_for_record_if_needed(api_base,
                                                               record_id)
    if did_fetch:
        # now go and authorize the token
        logging.debug("redirecting to authorize token")
        flask.redirect(smart.auth_redirect_url)
    if error_msg:
        return error_msg

    # ok, let's fetch demographics and display the name
    # NOTE: we fetched the demographics above to test the token,
    # maybe cache that result somewhere?
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

    return flask.render_template('index.html',
                                 api_base=api_base,
                                 record_id=record_id,
                                 record_name=record_name)


@app.route('/endpoint_select')
def endpoint():
    """ Shows all possible endpoints, sending the user back to index when
        one is chosen. """

    # get the callback NOTE: this is done very cheaply, we need to make
    # sure to end the callback url with either "?" or "&"
    callback = flask.request.args.get('callback', 'index.html?')
    if '?' != callback[-1] and '&' != callback[-1]:
        callback += '&' if '?' in callback else '?'

    available = []
    for api_base, srvr in settings.ENDPOINTS.iteritems():
        available.append({
            "name": srvr.get('name', 'Unnamed'),
            "url": api_base
        })

    return flask.render_template('endpoint_select.html',
                                 endpoints=available,
                                 callback=callback)


# ------------------------------------------------------------- Authorization
@app.route('/authorize')
def authorize():
    """ Extract the oauth_verifier and exchange it for an access token. """
    req_token = {'oauth_token': flask.request.args.get('oauth_token')}
    verifier = flask.request.args.get('oauth_verifier')
    api_base, record_id = _exchange_token(req_token, verifier)

    if record_id is not None:
        flask.redirect('/index.html?api_base=%s&record_id=%s' %
                       (api_base, record_id))

    # no record id
    flask.abort(400)

if __name__ == '__main__':
    app.run()
