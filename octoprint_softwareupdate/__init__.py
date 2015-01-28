# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"


import octoprint.plugin

import flask
import logging
import os
import threading
import time

from . import version_checks, updaters, exceptions, util


from octoprint.server.util.flask import restricted_access
from octoprint.util import dict_merge
import octoprint.settings


##~~ Plugin Metadata and Initialization


__plugin_name__ = "SoftwareUpdate"
__plugin_version__ = "0.1"
__plugin_description__ = "TODO"

def __plugin_init__():
	global _plugin
	_plugin = SoftwareUpdatePlugin()

	global __plugin_helpers__
	__plugin_helpers__ = dict(
		version_checks=version_checks,
		updaters=updaters,
		exceptions=exceptions,
		util=util
	)

	global __plugin_implementations__
	__plugin_implementations__ = [_plugin]


##~~ Settings


default_settings = {
	"checks": {
		"octoprint": {
			"type": "github_release",
			"user": "foosel",
			"repo": "OctoPrint",
			"update_script": "{{python}} \"{update_script}\" --python=\"{{python}}\" \"{{folder}}\" {{target}}".format(update_script=os.path.join(os.path.dirname(os.path.realpath(__file__)), "scripts", "update-octoprint.py")),
			"restart": "octoprint"
		},
	},

	"octoprint_restart_command": None,
	"environment_restart_command": None,

	"cache_ttl": 60,
}

check_defaults = {
	"check_type": None,
	# version_check: commandline
	"command": None,
	# version_check: git_commit
	"checkout_folder": None,
	# version_check: github_commit & github_release
	"user": None,
	"repo": None,
	"branch": None,
	# update_type: update_script
	"update_script": None,
	"update_folder": None,
	# update_type: pip
	"pip": None,
	"force_reinstall": None
}

s = octoprint.plugin.plugin_settings("softwareupdate", defaults=default_settings)

##~~ Blueprint

blueprint = flask.Blueprint("plugin.softwareupdate", __name__)

@blueprint.route("/check", methods=["GET"])
def check_for_update():
	global _plugin

	if "check" in flask.request.values:
		check_targets = map(str.strip, flask.request.values["check"].split(","))
	else:
		check_targets = None

	if "force" in flask.request.values and flask.request.values["force"] in octoprint.settings.valid_boolean_trues:
		force = True
	else:
		force=False

	try:
		information, update_available, update_possible = _plugin.get_current_versions(check_targets=check_targets, force=force)
		return flask.jsonify(dict(status="updatePossible" if update_available and update_possible else "updateAvailable" if update_available else "current", information=information))
	except exceptions.ConfigurationInvalid as e:
		flask.make_response("Update not properly configured, can't proceed: %s" % e.message, 500)


@blueprint.route("/update", methods=["POST"])
@restricted_access
def perform_update():
	global _plugin

	from octoprint.server import printer
	if printer.isPrinting() or printer.isPaused():
		# do not update while a print job is running
		flask.make_response("Printer is currently printing or paused", 409)

	if not "application/json" in flask.request.headers["Content-Type"]:
		flask.make_response("Expected content-type JSON", 400)

	json_data = flask.request.json

	if "check" in json_data:
		check_targets = map(str.strip, json_data["check"])
	else:
		check_targets = None

	if "force" in json_data:
		from octoprint.settings import valid_boolean_trues
		force = (json_data["force"] in valid_boolean_trues)
	else:
		force = False

	to_be_checked, checks = _plugin.perform_updates(check_targets=check_targets, force=force)
	return flask.jsonify(dict(order=to_be_checked, checks=checks))


##~~ Plugin


class SoftwareUpdatePlugin(octoprint.plugin.BlueprintPlugin,
                           octoprint.plugin.SettingsPlugin,
                           octoprint.plugin.AssetPlugin,
                           octoprint.plugin.TemplatePlugin):
	def __init__(self):
		self._logger = logging.getLogger("octoprint.plugins.softwareupdate")

		self._update_in_progress = False
		self._configured_checks_mutex = threading.Lock()
		self._configured_checks = None

		self._plugin_manager = None

		self._version_cache = dict()
		self._version_cache_ttl = s.getInt(["cache_ttl"]) * 60

	def _get_configured_checks(self):
		with self._configured_checks_mutex:
			if self._configured_checks is None:
				self._configured_checks = s.get(["checks"], merged=True)
				update_check_hooks = self.plugin_manager.get_hooks("octoprint.plugin.softwareupdate.check_config")
				for name, hook_checks in update_check_hooks.items():
					for key, data in hook_checks.items():
						if key in self._configured_checks:
							data = dict_merge(data, self._configured_checks[key])
						self._configured_checks[key] = data

			return self._configured_checks

	@property
	def plugin_manager(self):
		if self._plugin_manager is None:
			self._plugin_manager = octoprint.plugin.plugin_manager()
		return self._plugin_manager

	#~~ BluePrint API

	def get_blueprint(self):
		global blueprint
		return blueprint

	#~~ Asset API

	def get_assets(self):
		return dict(
			js=["js/softwareupdate.js"]
		)

	##~~ TemplatePlugin API

	def get_template_configs(self):
		return [
			dict(type="settings", name="Software Update")
		]

	#~~ Updater

	def get_current_versions(self, check_targets=None, force=False):
		"""
		Retrieves the current version information for all defined check_targets. Will retrieve information for all
		available targets by default.

		:param check_targets: an iterable defining the targets to check, if not supplied defaults to all targets
		"""

		checks = self._get_configured_checks()
		if check_targets is None:
			check_targets = checks.keys()

		update_available = False
		update_possible = False
		information = dict()

		for target, check in checks.items():
			if not target in check_targets:
				continue

			try:
				target_information, target_update_available, target_update_possible = self._get_current_version(target, check, force=force)
				if target_information is None:
					continue
			except exceptions.UnknownCheckType:
				self._logger.warn("Unknown update check type for %s" % target)
				continue

			target_information = dict_merge(dict(local=dict(name="unknown", value="unknown"), remote=dict(name="unknown", value="unknown")), target_information)

			update_available = update_available or target_update_available
			update_possible = update_possible or (target_update_possible and target_update_available)
			information[target] = dict(updateAvailable=target_update_available, updatePossible=target_update_possible, information=target_information)

			if "displayName" in check:
				information[target]["displayName"] = check["displayName"]

			if "displayVersion" in check:
				from octoprint._version import get_versions
				octoprint_version = get_versions()["version"]
				local_name = target_information["local"]["name"]
				local_value = target_information["local"]["value"]
				information[target]["displayVersion"] = check["displayVersion"].format(octoprint_version=octoprint_version, local_name=local_name, local_value=local_value)

		return information, update_available, update_possible

	def _get_current_version(self, target, check, force=False):
		"""
		Determines the current version information for one target based on its check configuration.
		"""

		if target in self._version_cache and not force:
			timestamp, information, update_available, update_possible = self._version_cache[target]
			if timestamp + self._version_cache_ttl >= time.time():
				return information, update_available, update_possible

		information = dict()
		update_available = False

		try:
			version_checker = self._get_version_checker(target, check)
			information, is_current = version_checker.get_latest(target, check)
			if information is not None and not is_current:
				update_available = True
		except exceptions.UnknownCheckType:
			self._logger.warn("Unknown check type %s for %s" % (check["type"], target))
			update_possible = False
		except:
			self._logger.exception("Could not check %s for updates" % target)
			update_possible = False
		else:
			try:
				updater = self._get_updater(target, check)
				update_possible = updater.can_perform_update(target, check)
			except:
				update_possible = False

		self._version_cache[target] = (time.time(), information, update_available, update_possible)
		return information, update_available, update_possible

	def _send_client_message(self, message_type, data=None):
		self.plugin_manager.send_plugin_message("softwareupdate", dict(type=message_type, data=data))

	def perform_updates(self, check_targets=None, force=False):
		"""
		Performs the updates for the given check_targets. Will update all possible targets by default.

		:param check_targets: an iterable defining the targets to update, if not supplied defaults to all targets
		"""

		checks = self._get_configured_checks()
		if check_targets is None:
			check_targets = checks.keys()
		to_be_updated = sorted(set(check_targets) & set(checks.keys()))
		if "octoprint" in to_be_updated:
			to_be_updated.remove("octoprint")
			tmp = ["octoprint"] + to_be_updated
			to_be_updated = tmp

		updater_thread = threading.Thread(target=self._update_worker, args=(checks, to_be_updated, force))
		updater_thread.daemon = False
		updater_thread.start()

		return to_be_updated, dict((key, check["displayName"] if "displayName" in check else key) for key, check in checks.items() if key in to_be_updated)

	def _update_worker(self, checks, check_targets, force):

		restart_type = None

		try:
			self._update_in_progress = True

			target_results = dict()
			error = False

			### iterate over all configured targets

			for target in check_targets:
				if not target in checks:
					continue
				check = checks[target]

				if "enabled" in check and not check["enabled"]:
					continue

				if not target in check_targets:
					continue

				target_error, target_result = self._perform_update(target, check, force)
				error = error or target_error
				if target_result is not None:
					target_results[target] = target_result

					if "restart" in check:
						target_restart_type = check["restart"]
					elif "pip" in check:
						target_restart_type = "octoprint"

					# if our update requires a restart we have to determine which type
					if restart_type is None or (restart_type == "octoprint" and target_restart_type == "environment"):
						restart_type = target_restart_type

		finally:
			# we might have needed to update the config, so we'll save that now
			s.save()

			# also, we are now longer updating
			self._update_in_progress = False

		if error:
			# if there was an unignorable error, we just return error
			self._send_client_message("error", dict(results=target_results))

		else:
			# otherwise the update process was a success, but we might still have to restart
			if restart_type is not None and restart_type in ("octoprint", "environment"):
				# one of our updates requires a restart of either type "octoprint" or "environment". Let's see if
				# we can actually perform that
				restart_command = s.get(["%s_restart_command" % restart_type])

				if restart_command is not None:
					self._send_client_message("restarting", dict(restart_type=restart_type, results=target_results))
					try:
						self._perform_restart(restart_command)
					except exceptions.RestartFailed:
						self._send_client_message("restart_failed", dict(restart_type=restart_type, results=target_results))
				else:
					# we don't have this restart type configured, we'll have to display a message that a manual
					# restart is needed
					self._send_client_message("restart_manually", dict(restart_type=restart_type, results=target_results))
			else:
				self._send_client_message("success", dict(results=target_results))

	def _perform_update(self, target, check, force):
		information, update_available, update_possible = self._get_current_version(target, check)

		if not update_available and not force:
			return False, None

		if not update_possible:
			self._logger.warn("Cannot perform update for %s, update type is not fully configured" % target)
			return False, None

		# determine the target version to update to
		target_version = information["remote"]["value"]
		target_error = False

		### The actual update procedure starts here...

		try:
			self._logger.info("Starting update of %s to %s..." % (target, target_version))
			self._send_client_message("updating", dict(target=target, version=target_version))
			updater = self._get_updater(target, check)
			if updater is None:
				raise exceptions.UnknownUpdateType()

			update_result = updater.perform_update(target, check, target_version)
			target_result = ("success", update_result)
			self._logger.info("Update of %s to %s successful!" % (target, target_version))

		except exceptions.UnknownUpdateType:
			self._logger.warn("Update of %s can not be performed, unknown update type" % target)
			self._send_client_message("update_failed", dict(target=target, version=target_version, reason="Unknown update type"))
			return False, None

		except Exception as e:
			self._logger.exception("Update of %s can not be performed" % target)
			if not "ignorable" in check or not check["ignorable"]:
				target_error = True

			if isinstance(e, exceptions.UpdateError):
				target_result = ("failed", e.data)
				self._send_client_message("update_failed", dict(target=target, version=target_version, reason=e.data))
			else:
				target_result = ("failed", None)
				self._send_client_message("update_failed", dict(target=target, version=target_version, reason="unknown"))

		else:
			# make sure that any external changes to config.yaml are loaded into the system
			s.load()

			# persist the new version if necessary for check type
			if check["type"] == "github_commit":
				checks = s.get(["checks"], merged=True)
				if target in checks:
					# TODO make this cleaner, right now it saves too much to disk
					checks[target]["current"] = target_version
					s.set(["checks"], checks)

		return target_error, target_result

	def _perform_restart(self, restart_command):
		"""
		Performs a restart using the supplied restart_command.
		"""

		self._logger.info("Restarting...")
		try:
			util.execute(restart_command)
		except exceptions.ScriptError as e:
			self._logger.exception("Error while restarting")
			self._logger.warn("Restart stdout:\n%s" % e.stdout)
			self._logger.warn("Restart stderr:\n%s" % e.stderr)
			raise exceptions.RestartFailed()

	def _get_version_checker(self, target, check):
		"""
		Retrieves the version checker to use for given target and check configuration. Will raise an UnknownCheckType
		if version checker cannot be determined.
		"""

		if not "type" in check:
			raise exceptions.ConfigurationInvalid("no check type defined")

		check_type = check["type"]
		if check_type == "github_release":
			if target == "octoprint":
				from octoprint._version import get_versions
				check["current"] = get_versions()["version"]
			return version_checks.github_release
		elif check_type == "github_commit":
			return version_checks.github_commit
		elif check_type == "git_commit":
			return version_checks.git_commit
		elif check_type == "commandline":
			return version_checks.commandline
		elif check_type == "python_checker":
			return version_checks.python_checker
		else:
			raise exceptions.UnknownCheckType()

	def _get_updater(self, target, check):
		"""
		Retrieves the updater for the given target and check configuration. Will raise an UnknownUpdateType if updater
		cannot be determined.
		"""

		if "update_script" in check:
			return updaters.update_script
		elif "pip" in check:
			return updaters.pip
		elif "python_updater" in check:
			return updaters.python_updater
		else:
			raise exceptions.UnknownUpdateType()

