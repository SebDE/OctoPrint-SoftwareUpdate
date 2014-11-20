$(function() {
    function SoftwareUpdateViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.popup = undefined;

        self.updateInProgress = false;
        self.waitingForRestart = false;
        self.restartTimeout = undefined;

        self.loginState.subscribe(function(event) {
            self.performCheck();
        });

        self._showPopup = function(options) {
            if (self.popup !== undefined) {
                self.popup.remove();
            }
            self.popup = new PNotify(options);
        };

        self.performCheck = function() {
            if (!self.loginState.isUser()) return;

            $.ajax({
                url: PLUGIN_BASEURL + "softwareupdate/check",
                type: "GET",
                dataType: "json",
                success: function(data) {
                    if (data.status == "updateAvailable") {
                        var options = {
                            title: gettext("Update Available"),
                            text: gettext("A new version of OctoPrint is available!"),
                            hide: false
                        };

                        if (self.loginState.isAdmin()) {
                            // if user is admin, add action buttons
                            options["confirm"] = {
                                confirm: true,
                                    buttons: [{
                                        text: gettext("Update now"),
                                        click: self.update
                                    }]
                            };
                            options["buttons"] = {
                                closer: false,
                                sticker: false
                            };
                        }

                        self._showPopup(options);
                    }
                }
            });
        };

        self.update = function() {
            if (self.updateInProgress) return;
            self.updateInProgress = true;

            // TODO: add confirmation dialog

            var options = {
                title: gettext("Updating..."),
                text: gettext("Now updating, please wait."),
                icon: "icon-cog icon-spin",
                hide: false,
                buttons: {
                    closer: false,
                    sticker: false
                }
            };
            self._showPopup(options);

            $.ajax({
                url: PLUGIN_BASEURL + "softwareupdate/update",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                complete: function() {
                    self.updateInProgress = false;
                },
                success: function(data) {
                    var options = undefined;

                    if (data.result == "success") {
                        options = {
                            title: gettext("Update successful, restarting!"),
                            text: gettext("The update finished successfully and the server will now be restarted. The page will reload automatically."),
                            type: "success",
                            hide: false,
                            buttons: {
                                sticker: false
                            }
                        };
                        self.waitingForRestart = true;
                        self.restartTimeout = setTimeout(function() {
                            self._showPopup({
                                title: gettext("Restart failed"),
                                test: gettext("The server apparently did not restart by itself, you'll have to do it manually. Please consult the log file on what went wrong."),
                                type: "error",
                                hide: false,
                                buttons: {
                                    sticker: false
                                }
                            });
                            self.waitingForRestart = false;
                        }, 10000);
                    } else if (data.result == "restart") {
                        options = {
                            title: gettext("Update successful, restart required!"),
                            text: gettext("The update finished successfully, please restart the server now."),
                            type: "success",
                            hide: false,
                            buttons: {
                                sticker: false
                            }
                        };
                    } else {
                        options = {
                            title: gettext("Update failed!"),
                            text: gettext("The update failed, please consult the log files."),
                            type: "error",
                            hide: false,
                            buttons: {
                                sticker: false
                            }
                        };
                    }

                    if (options === undefined) return;
                    self._showPopup(options);
                }
            });
        };

        self.onServerDisconnect = function() {
            if (self.restartTimeout !== undefined) {
                clearTimeout(self.restartTimeout);
            }
            return true;
        };

        self.onDataUpdaterReconnect = function() {
            if (self.waitingForRestart) {
                self.waitingForRestart = false;

                var options = {
                    title: gettext("Restart successful!"),
                    text: gettext("The server was restarted successfully. The page will now reload automatically."),
                    type: "success",
                    hide: false
                };
                self._showPopup(options);
            } else {
                self.performCheck();
            }
        };

        self.onStartup = self.performCheck;
    }

    // view model class, parameters for constructor, container to bind to
    ADDITIONAL_VIEWMODELS.push([SoftwareUpdateViewModel, ["loginStateViewModel"], undefined]);
});