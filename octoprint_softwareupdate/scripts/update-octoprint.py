#!/bin/env python
from __future__ import absolute_import

__author__ = "Gina Haeussge <osd@foosel.net>"
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

	return p.returncode, stdout


def _python(args, cwd, python_executable):
	try:
		p = subprocess.Popen([python_executable] + args, cwd=cwd, stdout=subprocess.PIPE,
		                     stderr=subprocess.PIPE)
	except:
		return None, None

	stdout = p.communicate()[0].strip()
	if sys.version >= "3":
		stdout = stdout.decode()

	return p.returncode, stdout


def update_source(git_executable, folder, target, force=False):
	print("Running: git pull")
	returncode, stdout = _git(["pull"], folder, git_executable=git_executable)
	if returncode != 0:
		raise RuntimeError("Could not update, \"git pull\" failed with returncode %d: %s" % (returncode, stdout))

	print("Running: git stash")
	returncode, stdout = _git(["stash"], folder, git_executable=git_executable)
	if returncode != 0:
		raise RuntimeError("Could not update, \"git stash\" failed with returncode %d: %s" % (returncode, stdout))

	reset_command = ["reset"]
	if force:
		reset_command += ["--hard"]
	reset_command += [target]

	print("Running: git %s" % " ".join(reset_command))
	returncode, stdout = _git(reset_command, folder, git_executable=git_executable)
	if returncode != 0:
		raise RuntimeError("Error while updating, \"git %s\" failed with returncode %d: %s" % (" ".join(reset_command), returncode, stdout))


def install_source(python_executable, folder):
	print("Running: python setup.py clean")
	returncode, stdout = _python(["setup.py", "clean"], folder, python_executable)
	if returncode != 0:
		raise RuntimeError("Could not update, \"python setup.py clean\" failed with returncode %d: %s" % (returncode, stdout))

	print("Running: python setup.py install")
	returncode, stdout = _python(["setup.py", "install"], folder, python_executable)
	if returncode != 0:
		raise RuntimeError("Could not update, \"python setup.py install\" failed with returncode %d: %s" % (returncode, stdout))


def parse_arguments():
	import argparse

	parser = argparse.ArgumentParser(prog="update-octoprint.py")

	parser.add_argument("--git", action="store", type=str, dest="git_executable",
	                    help="Specify git executable to use")
	parser.add_argument("--python", action="store", type=str, dest="python_executable",
	                    help="Specify python executable to use")
	parser.add_argument("--force", action="store_true", dest="force",
	                    help="Set this to force the update to overwrite and local changes")
	parser.add_argument("folder", type=str,
	                    help="Specify the base folder of the OctoPrint installation to update")
	parser.add_argument("target", type=str,
	                    help="Specify the commit or tag to which to update")

	args = parser.parse_args()

	return args

def main():
	args = parse_arguments()

	git_executable = None
	if args.git_executable:
		git_executable = args.git_executable

	python_executable = sys.executable
	if args.python_executable:
		python_executable = args.python_executable

	folder = args.folder
	target = args.target

	update_source(git_executable, folder, target, force=args.force)
	install_source(python_executable, folder)

if __name__ == "__main__":
	main()
