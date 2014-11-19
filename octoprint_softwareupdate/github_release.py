# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

import requests

__GITHUB_REPO_BASEURL = "https://api.github.com/repos/{user}/{repo}/"


def is_local_current(release_information):
	import semantic_version

	local_version = semantic_version.Version(release_information["local"]["value"])
	remote_version = semantic_version.Version(release_information["remote"]["value"])

	return local_version >= remote_version


def _get_latest_release(user, repo):
	r = requests.get(__GITHUB_REPO_BASEURL.format(user=user, repo=repo) + "releases")
	if not r.status_code == requests.codes.ok:
		return None

	releases = r.json()

	# filter out prereleases and drafts
	releases = filter(lambda rel: not rel["prerelease"] and not rel["draft"], releases)
	if not releases:
		return None

	# sort by date
	comp = lambda a, b: cmp(a["created_at"], b["created_at"])
	releases = sorted(releases, cmp=comp)

	# latest release = last in list
	latest = releases[-1]

	return latest["name"], latest["tag_name"]


def get_release_information(user, repo):
	from octoprint._version import get_versions
	current_version = get_versions()["version"]

	remote_name, remote_tag = _get_latest_release(user, repo)

	return dict(
		local=dict(name=current_version, value=current_version),
		remote=dict(name=remote_name, value=remote_tag)
	)
