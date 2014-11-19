# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"


import errno
import subprocess
import sys


def _get_git_executables():
	GITS = ["git"]
	if sys.platform == "win32":
		GITS = ["git.cmd", "git.exe"]
	return GITS


def _git(args, cwd, hide_stderr=False, verbose=False, git_executable=None):
	if git_executable is not None:
		commands = [git_executable]
	else:
		commands = _get_git_executables()

	for c in commands:
		try:
			p = subprocess.Popen([c] + args, cwd=cwd, stdout=subprocess.PIPE,
			                     stderr=(subprocess.PIPE if hide_stderr
			                             else None))
			break
		except EnvironmentError:
			e = sys.exc_info()[1]
			if e.errno == errno.ENOENT:
				continue
			if verbose:
				print("unable to run %s" % args[0])
				print(e)
			return None, None
	else:
		if verbose:
			print("unable to find command, tried %s" % (commands,))
		return None, None

	stdout = p.communicate()[0].strip()
	if sys.version >= '3':
		stdout = stdout.decode()

	if p.returncode != 0:
		if verbose:
			print("unable to run %s (error)" % args[0])
		return p.returncode, None

	return p.returncode, stdout


def is_local_current(commit_information):
	local_commit = commit_information["local"]["value"]
	remote_commit = commit_information["remote"]["value"]
	return local_commit == remote_commit


def get_latest_commit(cwd, git_executable=None):
	from octoprint._version import get_versions
	current_version = get_versions()["version"]

	returncode, _ = _git(["fetch"], cwd, verbose=True, git_executable=git_executable)
	if returncode != 0:
		return None

	returncode, local_commit = _git(["rev-parse", "@{0}"], cwd, verbose=True, git_executable=git_executable)
	if returncode != 0:
		return None

	returncode, remote_commit = _git(["rev-parse", "@{u}"], cwd, verbose=True, git_executable=git_executable)
	if returncode != 0:
		return None

	return_code, base = _git(["merge-base", "@{0}", "@{u}"], cwd, verbose=True, git_executable=git_executable)
	if returncode != 0:
		return None

	if local_commit == remote_commit or remote_commit == base:
		return dict(
			local=dict(name=current_version, value=local_commit),
			remote=dict(name="Up to date", value=local_commit)
		)

	returncode, log = _git(["log", "{local_commit}..{remote_commit}".format(**locals()), "--oneline"], cwd, verbose=True, git_executable=git_executable)
	if returncode != 0:
		return None

	count = len(filter(lambda x: len(x.strip()), log.splitlines()))

	return dict(
		local=dict(name=current_version, value=local_commit),
		remote=dict(name="Incoming changes".format(count=count), value=remote_commit)
	)
