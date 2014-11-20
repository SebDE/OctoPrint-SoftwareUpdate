# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"


import octoprint.plugin

import flask
import logging
import os
import sys

from . import github_release, git_commit

from octoprint.server.util.flask import restricted_access

__plugin_name__ = "softwareupdate"
__plugin_version__ = "0.1"
__plugin_description__ = ""

def __plugin_init__():
	global _plugin
	_plugin = SoftwareUpdatePlugin()

	global __plugin_implementations__
	__plugin_implementations__ = [_plugin]


default_settings = {
	"checkout_folder": None,
	"python_executable": sys.executable,
	"git_executable": None,
	"check_type": "release",
	"octoprint_update_script": "{{python}} \"{update_script}\" --python=\"{{python}}\" \"{{folder}}\" {{target}}".format(update_script=os.path.join(os.path.dirname(os.path.realpath(__file__)), "scripts", "update-octoprint.py")),
	"octoprint_restart_command": None
}
s = octoprint.plugin.plugin_settings("softwareupdate", defaults=default_settings)

blueprint = flask.Blueprint("plugin.softwareupdate", __name__)

@blueprint.route("/check", methods=["GET"])
def check_for_update():
	if "type" in flask.request.values:
		check_type = flask.request.values["type"]
	else:
		check_type = s.get(["check_type"])

	if not check_type in ("release", "commit"):
		flask.make_response("Unknown check type: %s" % check_type, 400)

	information, update_available = _get_current_information(check_type)

	return flask.jsonify(dict(status="updateAvailable" if update_available else "current", information=information))


@blueprint.route("/update", methods=["POST"])
@restricted_access
def perform_update():
	logger = logging.getLogger("octoprint.plugins.softwareupdate")

	update_script = s.get(["octoprint_update_script"])
	if not update_script:
		flask.make_response("Update script not properly configured, can't update", 500)

	folder = s.get(["checkout_folder"])
	if not folder:
		flask.make_response("Checkout folder is not configured, can't update", 500)

	python_executable = s.get(["python_executable"])

	if "type" in flask.request.values:
		check_type = flask.request.values["type"]
	else:
		check_type = s.get(["check_type"])

	if not check_type in ("release", "commit"):
		flask.make_response("Unknown check type: %s" % check_type, 400)

	information, update_available = _get_current_information(check_type)
	if not update_available:
		flask.make_response("No update available!", 400) # TODO other status code?

	command = update_script.format(python=python_executable, folder=folder, target=information["remote"]["value"])
	p = None

	logger.info("Starting update to %s..." % information["remote"]["value"])

	import sarge
	try:
		p = sarge.run(command, cwd=folder, stdout=sarge.Capture(), stderr=sarge.Capture())
	except:
		logger.exception("Error while executing update script")
		if p is not None and p.stderr is not None:
			logger.warn("Update stdout:\n%s" % p.stdout.text)
			logger.warn("Update stderr:\n%s" % p.stderr.text)
		return flask.jsonify(dict(result="error", stdout=p.stdout.text if p is not None and p.stdout.text is not None else "", stderr=p.stderr.text if p is not None and p.stderr.text is not None else ""))
	else:
		logger.debug("Update stdout:\n%s" % p.stdout.text)
		logger.debug("Update stderr:\n%s" % p.stderr.text)
		logger.info("Update to %s successful!" % information["remote"]["value"])

	restart_command = s.get(["octoprint_restart_command"])
	if restart_command is None:
		return flask.jsonify(dict(result="restart", stdout=p.stdout.text, stderr=p.stderr.text))

	def restart_handler(restart_command):
		logger.info("Restarting...")

		p = None
		try:
			p = sarge.run(restart_command, stdout=sarge.Capture(), stderr=sarge.Capture())
		except:
			logger.exception("Error while restarting server")
			if p is not None and p.stderr is not None:
				logger.warn("Restart stdout:\n%s" % p.stdout.text)
				logger.warn("Restart stderr:\n%s" % p.stderr.text)
		else:
			logger.debug("Restart stdout:\n%s" % p.stdout.text)
			logger.debug("Restart stderr:\n%s" % p.stderr.text)

	import threading
	restart_thread = threading.Thread(target=restart_handler, args=(restart_command))
	restart_thread.daemon = True
	restart_thread.start()

	return flask.jsonify(dict(result="success", stdout=p.stdout.text, stderr=p.stderr.text))


def _get_current_information(check_type):
	information = dict()
	update_available = False

	if check_type == "release":
		# check for new release
		release_information = github_release.get_release_information("foosel", "OctoPrint")
		if release_information is not None:
			information = release_information
			if not github_release.is_local_current(release_information):
				update_available = True

	elif check_type == "commit":
		# check for new commits
		cwd = s.get(["checkout_folder"])
		if not cwd:
			flask.make_response("Checkout folder is not configured, can't check for updates", 500)

		commit_information = git_commit.get_latest_commit(cwd, git_executable=s.get(["git_executable"]))
		if commit_information is not None:
			information = commit_information
			if not git_commit.is_local_current(commit_information):
				update_available = True

	return information, update_available


class SoftwareUpdatePlugin(octoprint.plugin.BlueprintPlugin,
                           octoprint.plugin.SettingsPlugin,
                           octoprint.plugin.AssetPlugin):

	def get_blueprint(self):
		global blueprint
		return blueprint

	def get_asset_folder(self):
		return os.path.join(os.path.dirname(os.path.realpath(__file__)), "static")

	def get_assets(self):
		return dict(
			js=["js/softwareupdate.js"]
		)



