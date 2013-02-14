SMART REST Sample App
=====================

This is a simple SMART REST example app. It is a Python [Bottle] app and uses our [Python client][client], you can use it to get the hang of the basic SMART flow or as a bootstrap for your own REST app.

### Get the App ###

```bash
git checkout git://github.com/chb/smart_rest_sample.git
git submodule update --init --recursive
```

### Run the App ###

Python modules you will need:

* bottle
* oauth2
* rdflib
* rdfextras
* jinja2

Then just run the `server.py` script, it will run a local webserver on port `8008`. To register the app on a SMART container you can use the supplied `manifest.json` file.

The `wsgi.py` file is where the request-to-Python mapping happens. Our app defines three URLs:

* `index`: The main URL
* `endpoint_select`: Where we show the possible endpoints
* `authorize`: For the OAuth callback

### AppFog ###

The app has a `requirements.txt` file and can readily be used as a bottle-app on [AppFog].

[bottle]: http://bottlepy.org/
[client]: https://github.com/chb/smart_client_python
[appfog]: https://www.appfog.com


REST App Behavior
=================

When you design your SMART app you may want to ensure that it can talk to different SMART containers. This app shows one way on how you can handle different containers:

Settings
--------

Your app needs to know the consumer-key and -secret for the container it is enabled for. For this we create the file `settings.py`:

```python
ENDPOINTS = {
	"http://sandbox.smartplatforms.org:7000": {
		"name": "SMART Sandbox",
		"app_id": "app@apps.chip.org",
		"consumer_key": "app@apps.chip.org",
		"consumer_secret": "abcdefg"
	},
	"http://localhost:7000": {
		"name": "Localhost",
		"app_id": "app@apps.chip.org",
		"consumer_key": "app@apps.chip.org",
		"consumer_secret": "hijklmn"
	}
}
```

This defines two containers that your app has a key and a secret for, one is our sandbox and one could be a local SMART installation for testing.


App Launch Flow
---------------

The `index` URL of your app is defined in the manifest, and this URL will be called by the container when a user launches your app. When your app is launched from a SMART container you will receive two parameters:

* `api_base`: The base URL of the SMART container
* `record_id`: The record id against which to run your app

If your app can also run in its own window and a user launches your app this way, the first request possibly does not contain either parameters.

### api_base ###

First thing you check for, when your index page is requested, is whether you have an `api_base` parameter. If you have one and you know the server behind that URL (by looking in the settings file we created above) you can go to the next step.

If there is no `api_base` parameter you can opt to display a **Select SMART Container** page where you list the servers defined in your settings file. We do that by redirecting to `/endpoint_select`. When the user selects a server you just call your index page again, supplying the `api_base` parameter.

### record_id ###

Once you have a server, check for the `record_id`. If it is missing you can have the user choose a record by redirecting it to the **app_launch** URL defined in the server's manifest. If you're using our Python client you can just redirect to `smart_client.launch_url`.  
The user will be prompted to login and select a record. Upon selecting a record the user will return to your index page with both `api_base` and `record_id` set.


OAuth Dance
-----------

At this point you should have both parameters and you can start the OAuth dance. The sample app stores the tokens with their associated api_base and record_id in a local sqlite database, see `tokenstore.py` for details.
