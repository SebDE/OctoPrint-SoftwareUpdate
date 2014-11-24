# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

import sys
import logging

from ..exceptions import ScriptError, ConfigurationInvalid, UpdateError
from ..util import execute


def can_perform_update(target, check):
	return "checkout_folder" in check or "update_folder" in check


def perform_update(target, check, target_version):
	logger = logging.getLogger("octoprint.plugin.softwareupdate.updater.update_script")

	if not can_perform_update(target, check):
		raise ConfigurationInvalid("checkout_folder and update_folder are missing for update target %s, one is needed" % target)

	update_script = check["update_script"]
	folder = check["update_folder"] if "update_folder" in check else check["checkout_folder"]
	pre_update_script = check["pre_update_script"] if "pre_update_script" in check else None
	post_update_script = check["post_update_script"] if "post_update_script" in check else None

	update_stdout = ""
	update_stderr = ""

	### pre update

	if pre_update_script is not None:
		logger.info("Running pre-update script...")
		try:
			returncode, stdout, stderr = execute(pre_update_script, cwd=folder)
			update_stdout += stdout
			update_stderr += stderr
		except ScriptError as e:
			logger.exception("Error while executing pre update script, got returncode %r" % e.returncode)
			logger.warn("Pre-Update stdout:\n%s" % e.stdout)
			logger.warn("Pre-Update stderr:\n%s" % e.stderr)

	### update

	try:
		update_command = update_script.format(python=sys.executable, folder=folder, target=target_version)
		returncode, stdout, stderr = execute(update_command, cwd=folder)
		update_stdout += stdout
		update_stderr += stderr
	except ScriptError as e:
		logger.exception("Error while executing update script, got returncode %r" % e.returncode)
		logger.warn("Update stdout:\n%s" % e.stdout)
		logger.warn("Update stderr:\n%s" % e.stderr)
		raise UpdateError((e.stdout, e.stderr))

	### post update

	if post_update_script is not None:
		logger.info("Running post-update script...")
		try:
			returncode, stdout, stderr = execute(post_update_script, cwd=folder)
			update_stdout += stdout
			update_stderr += stderr
		except ScriptError as e:
			logger.exception("Error while executing post update script, got returncode %r" % e.returncode)
			logger.warn("Post-Update stdout:\n%s" % e.stdout)
			logger.warn("Post-Update stderr:\n%s" % e.stderr)

	logger.debug("Update stdout:\n%s" % update_stdout)
	logger.debug("Update stderr:\n%s" % update_stderr)

	### result

	return update_stdout, update_stderr
