#!/usr/bin/env python
#
# 2013-02-12  Created by Pascal Pfiffner

import os.path
from os import makedirs
from sqlite import SQLite

DB_FILE = 'tokens.db'


class TokenStore(object):
    """ A class to handle OAuth Tokens. """

    did_setup = False

    def __init__(self):
        self.sqlite = SQLite.get(DB_FILE)

    # --------------------------------------------------------- Token Storage
    def tokenForRecord(self, api_base, record_id):
        """ Returns the desired token as a dict in the form:
            {
                'oauth_token': token
                'oauth_token_secret': secret
            }
        """
        query = """SELECT token, secret
                     FROM record_tokens
                    WHERE record_id = ? AND on_server = ?"""

        res = self.sqlite.executeOne(query, (record_id, api_base))
        if res is None:
            return None

        return {
            'oauth_token': res[0],
            'oauth_token_secret': res[1]
        }

    def tokenServerRecordForToken(self, token):
        """ Returns a token/secret dict, server url and the record id as
        a tuple (if the token is known). """

        query = """SELECT token, secret, on_server, record_id
                     FROM record_tokens
                    WHERE token = ?"""

        res = self.sqlite.executeOne(query, (token.get('oauth_token'),))
        if res is None:
            return None, None

        return {
            'oauth_token': res[0],
            'oauth_token_secret': res[1]
        }, res[2], res[3]

    def storeTokenForRecord(self, api_base, record_id, token):
        """ Stores a token.

            Note that record/server combinations are unique, older pairs
            will be replaced by this call. You must provide the token as a
            dictionary with "oauth_token" and "oauth_token_secret" keys.
        """
        query = """INSERT OR REPLACE INTO record_tokens
                   (record_id, on_server, token, secret) VALUES (?, ?, ?, ?)"""
        params = (record_id, api_base, token.get('oauth_token'),
                  token.get('oauth_token_secret'))
        if 0 == self.sqlite.executeInsert(query, params):
            return False

        self.sqlite.commit()
        return True

    def removeRecordToken(self, token):
        """ Deletes a token.

            You must provide the token as a dictionary with at least the
            "oauth_token" key.
        """
        query = "DELETE FROM record_tokens WHERE token = ?"
        self.sqlite.execute(query, (token.get('oauth_token'),))
        self.sqlite.commit()
        return True

    # ----------------------------------------------------------------- Setup
    @classmethod
    def setup(cls):
        """ Makes sure we have a database. """

        if cls.did_setup:
            return

        # init the database if needed
        if not os.path.exists(DB_FILE):

            # make sure the parent directory exists
            if (len(os.path.dirname(DB_FILE)) > 0 and
                    not os.path.exists(os.path.dirname(DB_FILE))):
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
                token VARCHAR,
                secret VARCHAR,
                added TIMESTAMP,
                CONSTRAINT record_server UNIQUE (record_id, on_server) ON CONFLICT REPLACE
                )''')
            sql.execute("CREATE INDEX IF NOT EXISTS record_index ON record_tokens (record_id)")
            sql.execute("CREATE INDEX IF NOT EXISTS server_index ON record_tokens (on_server)")
            sql.execute("CREATE INDEX IF NOT EXISTS token_index ON record_tokens (token)")

        cls.did_setup = True

# run setup when imported
TokenStore.setup()
