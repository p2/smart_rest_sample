#!/usr/bin/env python
#
#	2013-02-12	Created by Pascal Pfiffner
#


import os.path
from os import makedirs
from uuid import uuid4

from sqlite import SQLite


DB_FILE = 'tokens.db'


class TokenStore(object):
	""" A class to handle OAuth Tokens
	"""
	
	did_setup = False
	
	def __init__(self):
		self.sqlite = SQLite.get(DB_FILE)
	
	
	# -------------------------------------------------------------------------- Token Storage
	def tokenServerRecordForToken(self, token):
		""" Returns a token/secret dict, server url and the record id as a tuple (if the token is known) """
		query = "SELECT token, secret, on_server, record_id FROM record_tokens WHERE token = ?"
		res = self.sqlite.executeOne(query, (token.get('oauth_token'),))
		if res is None:
			return None, None, None
		
		return {
			'oauth_token': res[0],
			'oauth_token_secret': res[1]
		}, res[2], res[3]
	
	def tokenServerRecordForCookie(self, cookie):
		""" Returns a token/secret dict, server url and the record id as a tuple (if the token is known) """
		query = "SELECT token, secret, on_server, record_id FROM record_tokens WHERE cookie = ?"
		res = self.sqlite.executeOne(query, (cookie,))
		if res is None:
			return None, None, None
		
		return {
			'oauth_token': res[0],
			'oauth_token_secret': res[1]
		}, res[2], res[3]
	
	def storeTokenForRecord(self, api_base, record_id, token):
		""" Stores a token and returns the cookie hash.
		Note that record/server combinations are unique, older pairs will be replaced by this call. You must provide
		the token as a dictionary with "oauth_token" and "oauth_token_secret" keys.
		"""
		cookie = unicode(uuid4())
		query = """INSERT OR REPLACE INTO record_tokens
			(record_id, on_server, cookie, token, secret)
			VALUES (?, ?, ?, ?, ?)"""
		params = (record_id, api_base, cookie, token.get('oauth_token'), token.get('oauth_token_secret'))
		if 0 == self.sqlite.executeInsert(query, params):
			return None
		
		self.sqlite.commit()
		return cookie
	
	def removeRecordToken(self, token):
		""" Deletes a token
		You must provide the token as a dictionary with at least the "oauth_token" key.
		"""
		query = "DELETE FROM record_tokens WHERE token = ?"
		self.sqlite.execute(query, (token.get('oauth_token'),))
		self.sqlite.commit()
		return True
	
	
	# -------------------------------------------------------------------------- Setup
	@classmethod
	def setup(cls):
		""" Makes sure we have a database """
		
		if cls.did_setup:
			return
		
		# init the database if needed
		if not os.path.exists(DB_FILE):
			
			# make sure the parent directory exists
			if len(os.path.dirname(DB_FILE)) > 0 \
				and not os.path.exists(os.path.dirname(DB_FILE)):
				try:
					os.makedirs(os.path.dirname(DB_FILE))
				except Exception, e:
					print "Failed to create %s: %s" % (os.path.dirname(DB_FILE), e)
					return
			
			# database init
			sql = SQLite.get(DB_FILE)
			sql.create('record_tokens', '''(
					token_id INTEGER PRIMARY KEY,
					record_id INT,
					on_server VARCHAR,
					cookie VARCHAR,
					token VARCHAR,
					secret VARCHAR,
					added TIMESTAMP,
					CONSTRAINT record_server UNIQUE (record_id, on_server) ON CONFLICT REPLACE
				)''')
			sql.execute("CREATE INDEX IF NOT EXISTS record_index ON record_tokens (record_id)")
			sql.execute("CREATE INDEX IF NOT EXISTS server_index ON record_tokens (on_server)")
			sql.execute("CREATE INDEX IF NOT EXISTS cookie_index ON record_tokens (cookie)")
			sql.execute("CREATE INDEX IF NOT EXISTS token_index ON record_tokens (token)")
		
		cls.did_setup = True


# run setup when imported
TokenStore.setup()			
			
