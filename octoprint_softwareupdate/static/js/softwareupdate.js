$(function() {
    function SoftwareUpdateViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];

        self.loginState.subscribe(function(event) {
            self.performCheck();
        });

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

                        new PNotify(options);
                    }
                }
            });
        };

        self.update = function() {
            // TODO: add confirmation dialog

            $.ajax({
                url: PLUGIN_BASEURL + "softwareupdate/update",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                success: function(data) {
                    if (data.result == "success") {
                        var options = {
                            title: gettext("Update successful!"),
                            text: gettext("The update finished successfully and the server was restarted. The page will reload automatically in 5 seconds"),
                            type: "success",
                            hide: false
                        };

                        new PNotify(options);
                    } else if (data.result == "restart") {
                        new PNotify({
                            title: gettext("Update successful, restart required!"),
                            text: gettext("The update finished successfully, please restart the server now."),
                            type: "success",
                            hide: false
                        });
                    } else {
                        new PNotify({
                            title: gettext("Update failed!"),
                            text: gettext("The update failed, please consult the log files."),
                            type: "error",
                            hide: false
                        });
                    }

                }
            });
        };

        self.onStartup = self.performCheck;
        self.onDataUpdaterReconnect = self.performCheck;
    }

    // view model class, parameters for constructor, container to bind to
    ADDITIONAL_VIEWMODELS.push([SoftwareUpdateViewModel, ["loginStateViewModel"], undefined]);
});