# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"


from ..exceptions import ConfigurationInvalid
from ..util import execute

def get_latest(target, check):
	if not "command" in check:
		raise ConfigurationInvalid("Update configuration for %s of type commandline needs command defined" % target)

	returncode, stdout, stderr = execute(check["command"], evaluate_returncode=False)

	# We expect command line check commands to
	#
	# * have a return code of 0 if an update is available, a value != 0 otherwise
	# * return the display name of the new version as the final line on stdout
	# * return the display name of the current version as the next to final line on stdout
	#
	# Example output:
	# 1.1.0
	# 1.1.1
	#
	# 1.1.0 is the current version, 1.1.1 is the remote version. If only one line is output, it's taken to be the
	# display name of the new version

	stdout_lines = filter(lambda x: len(x.strip()), stdout.splitlines())
	local_name = stdout_lines[-2] if len(stdout_lines) >= 2 else "unknown"
	remote_name = stdout_lines[-1] if len(stdout_lines) >= 1 else "unknown"
	is_current = returncode != 0

	information =dict(
		local=local_name,
		remote=dict(
			name=remote_name,
			value=not is_current
		)
	)
	return information, is_current