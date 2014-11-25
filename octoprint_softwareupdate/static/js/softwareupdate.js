$(function() {
    function SoftwareUpdateViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.printerState = parameters[1];
        self.popup = undefined;

        self.updateInProgress = false;
        self.waitingForRestart = false;
        self.restartTimeout = undefined;

        self.currentlyBeingUpdated = [];

        self.loginState.subscribe(function(event) {
            self.performCheck();
        });

        self._showPopup = function(options) {
            if (self.popup !== undefined) {
                self.popup.remove();
            }
            self.popup = new PNotify(options);
        };

        self._updatePopup = function(options) {
            if (self.popup === undefined) {
                self._showPopup(options);
            } else {
                self.popup.update(options);
            }
        };

        self.performCheck = function(force) {
            if (!self.loginState.isUser()) return;

            $.ajax({
                url: PLUGIN_BASEURL + "softwareupdate/check",
                type: "GET",
                dataType: "json",
                success: function(data) {
                    if (data.status == "updateAvailable" || data.status == "updatePossible") {
                        var text = gettext("There are updates available for the following components:");

                        // sort our keys
                        var sorted_keys = _.sortBy(_.keys(data.information), function(item) {
                            if (item == "octoprint") {
                                return "";
                            } else {
                                return item
                            }
                        });

                        text += "<ul>";
                        _.each(sorted_keys, function(key) {
                            var update_info = data.information[key];
                            if (update_info.updateAvailable) {
                                var displayName = key;
                                if (update_info.hasOwnProperty("displayName")) {
                                    displayName = update_info.displayName;
                                }
                                text += "<li>" + displayName + (update_info.updatePossible ? " <i class=\"icon-ok\"></i>" : "") + "</li>";
                            }
                        });
                        text += "</ul>";

                        text += "<small>" + gettext("Those components marked with <i class=\"icon-ok\"></i> can be updated directly.") + "</small>";

                        var options = {
                            title: gettext("Update Available"),
                            text: text,
                            hide: false
                        };

                        if (data.status == "updatePossible" && self.loginState.isAdmin()) {
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
                    } else if (data.status == "current" && force !== undefined && force) {
                        self._showPopup({
                            title: gettext("Everything is up-to-date"),
                            hide: false,
                            type: "success"
                        });
                    }
                }
            });
        };

        self.performUpdate = function() {
            self.updateInProgress = true;

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
                error: function() {
                    self._showPopup({
                        title: gettext("Update not started!"),
                        text: gettext("The update could not be started. Is it already active? Please consult the log for details."),
                        type: "error",
                        hide: false,
                        buttons: {
                            sticker: false
                        }
                    });
                },
                success: function(data) {
                    var options = undefined;

                    self.currentlyBeingUpdated = data.checks;

                    /*
                    if (data.result == "success") {
                        options = {
                            title: gettext("Update successful!"),
                            text: gettext("The update finished successfully."),
                            type: "success",
                            hide: false,
                            buttons: {
                                sticker: false
                            }
                        };
                    } else if (data.result == "restarting") {
                        options = {
                            title: gettext("Update successful, restarting!"),
                            text: gettext("The update finished successfully and the server will now be restarted."),
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
                    } else if (data.result == "restart_octoprint" || data.result == "restart_environment") {
                        var text = gettext("The update finished successfully, please restart OctoPrint now.");
                        if (data.result == "restart_environment") {
                            text = gettext("The update finished successfully, please reboot the server now.");
                        }

                        options = {
                            title: gettext("Update successful, restart required!"),
                            text: text,
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
                    */

                    if (options === undefined) return;
                    self._showPopup(options);
                }
            });
        };

        self.update = function() {
            if (self.updateInProgress) return;

            if (self.printerState.isPrinting()) {
                new PNotify({
                    title: gettext("Can't update while printing"),
                    text: gettext("A print job is currently in progress. Updating will be prevented until it is done."),
                    type: "error"
                });
            } else {
                $("#confirmation_dialog .confirmation_dialog_message").text(gettext("This will update your OctoPrint installation and restart the server."));
                $("#confirmation_dialog .confirmation_dialog_acknowledge").unbind("click");
                $("#confirmation_dialog .confirmation_dialog_acknowledge").click(function(e) {
                    e.preventDefault();
                    $("#confirmation_dialog").modal("hide");
                    self.performUpdate();
                });
                $("#confirmation_dialog").modal("show");
            }

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
            }
        };

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "softwareupdate") {
                return;
            }

            var messageType = data.type;
            var messageData = data.data;

            var options = undefined;

            switch (messageType) {
                case "updating": {
                    console.log(JSON.stringify(messageData));
                    self._updatePopup({
                        text: _.sprintf(gettext("Now updating %(name)s to %(version)s"), {name: self.currentlyBeingUpdated[messageData.target], version: messageData.version})
                    });
                    break;
                }
                case "restarting": {
                    console.log(JSON.stringify(messageData));

                    options = {
                        title: gettext("Update successful, restarting!"),
                        text: gettext("The update finished successfully and the server will now be restarted."),
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
                    }, 20000);

                    break;
                }
                case "restart_manually": {
                    console.log(JSON.stringify(messageData));

                    var restartType = messageData.restart_type;
                    var text = gettext("The update finished successfully, please restart OctoPrint now.");
                    if (restartType == "environment") {
                        text = gettext("The update finished successfully, please reboot the server now.");
                    }

                    options = {
                        title: gettext("Update successful, restart required!"),
                        text: text,
                        type: "success",
                        hide: false,
                        buttons: {
                            sticker: false
                        }
                    };
                    break;
                }
                case "restart_failed": {
                    var restartType = messageData.restart_type;
                    var text = gettext("Restarting OctoPrint failed, please restart it manually. You might also want to consult the log file on what went wrong here.");
                    if (restartType == "environment") {
                        text = gettext("Rebooting the server failed, please reboot it manually. You might also want to consult the log file on what went wrong here.");
                    }

                    options = {
                        title: gettext("Restart failed"),
                        test: gettext("The server apparently did not restart by itself, you'll have to do it manually. Please consult the log file on what went wrong."),
                        type: "error",
                        hide: false,
                        buttons: {
                            sticker: false
                        }
                    };
                    self.waitingForRestart = false;
                    break;
                }
                case "success": {
                    options = {
                        title: gettext("Update successful!"),
                        text: gettext("The update finished successfully."),
                        type: "success",
                        hide: false,
                        buttons: {
                            sticker: false
                        }
                    };
                    break;
                }
                case "error": {
                    self._showPopup({
                        title: gettext("Update failed!"),
                        text: gettext("The update did not finish successfully. Please consult the log for details."),
                        type: "error",
                        hide: false,
                        buttons: {
                            sticker: false
                        }
                    });
                    break;
                }
            }

            if (options != undefined) {
                self._showPopup(options);
            }
        };

    }

    // view model class, parameters for constructor, container to bind to
    ADDITIONAL_VIEWMODELS.push([SoftwareUpdateViewModel, ["loginStateViewModel", "printerStateViewModel"], document.getElementById("settings_plugin_softwareupdate_dialog")]);
});