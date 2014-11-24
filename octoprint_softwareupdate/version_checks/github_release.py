# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"

import requests
from ..exceptions import ConfigurationInvalid

RELEASE_URL = "https://api.github.com/repos/{user}/{repo}/releases"


def _get_latest_release(user, repo, include_prerelease=False):
	r = requests.get(RELEASE_URL.format(user=user, repo=repo))
	if not r.status_code == requests.codes.ok:
		return None

	releases = r.json()

	# filter out prereleases and drafts
	if include_prerelease:
		releases = filter(lambda rel: not rel["draft"], releases)
	else:
		releases = filter(lambda rel: not rel["prerelease"] and not rel["draft"], releases)

	if not releases:
		return None

	# sort by date
	comp = lambda a, b: cmp(a["created_at"], b["created_at"])
	releases = sorted(releases, cmp=comp)

	# latest release = last in list
	latest = releases[-1]

	return latest["name"], latest["tag_name"]


def _is_current(release_information):
	import semantic_version

	local_version = semantic_version.Version(release_information["local"])
	remote_version = semantic_version.Version(release_information["remote"]["value"])

	return local_version >= remote_version


def get_latest(target, check):
	if not "user" in check or not "repo" in check or not "current" in check:
		raise ConfigurationInvalid("github_release update configuration for %s needs user, repo and current set" % target)

	remote_name, remote_tag = _get_latest_release(check["user"], check["repo"])

	information =dict(
		local=check["current"],
		remote=dict(name=remote_name, value=remote_tag)
	)
	return information, _is_current(information)