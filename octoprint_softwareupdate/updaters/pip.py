# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"


try:
	import pip as _pip
except:
	_pip = None


def can_perform_update(target, check):
	return "pip" in check and _pip is not None


def perform_update(target, check, target_version):
	pip_args = ["install", check["pip"].format(target_version=target_version)]
	if "force_reinstall" in check and check["force_reinstall"]:
		pip_args += ["--upgrade", "--force-reinstall"]

	_pip.main(pip_args)
	return "ok"
