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
	_pip.main(pip_args)

	if "force_reinstall" in check and check["force_reinstall"]:
		# if force_reinstall is true, we need to install the package a second time, this time forcing its reinstall
		# without forcing its dependencies too
		pip_args += ["--ignore-installed", "--force-reinstall", "--no-deps"]
		_pip.main(pip_args)

	return "ok"
