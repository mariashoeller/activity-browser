import os
from PySide2 import QtGui, QtWidgets
from PySide2.QtCore import QSize, QUrl, Slot

from activity_browser import actions, signals
from activity_browser.mod import bw2data as bd

from ..info import __version__ as ab_version
from .icons import qicons

AB_BW25 = True if os.environ.get("AB_BW25", False) else False


class MenuBar(QtWidgets.QMenuBar):
    def __init__(self, window):
        super().__init__(parent=window)
        self.window = window
        self.file_menu = QtWidgets.QMenu("&Project", self.window)
        self.view_menu = QtWidgets.QMenu("&View", self.window)
        self.windows_menu = QtWidgets.QMenu("&Windows", self.window)
        self.tools_menu = QtWidgets.QMenu("&Tools", self.window)
        self.help_menu = QtWidgets.QMenu("&Help", self.window)

        self.new_proj_action = actions.ProjectNew.get_QAction()
        self.dup_proj_action = actions.ProjectDuplicate.get_QAction()
        self.delete_proj_action = actions.ProjectDelete.get_QAction()
        self.import_proj_action = actions.ProjectImport.get_QAction()
        self.export_proj_action = actions.ProjectExport.get_QAction()
        self.import_db_action = actions.DatabaseImport.get_QAction()
        self.export_db_action = actions.DatabaseExport.get_QAction()
        self.update_biosphere_action = actions.BiosphereUpdate.get_QAction()
        self.manage_settings_action = actions.SettingsWizardOpen.get_QAction()
        self.manage_plugins_action = actions.PluginWizardOpen.get_QAction()

        self.addMenu(self.file_menu)
        self.addMenu(self.view_menu)
        self.addMenu(self.tools_menu)
        self.addMenu(self.help_menu)

        self.setup_file_menu()
        self.setup_view_menu()
        self.setup_tools_menu()
        self.setup_help_menu()
        self.connect_signals()

    def connect_signals(self):
        bd.projects.current_changed.connect(self.biosphere_exists)
        bd.databases.metadata_changed.connect(self.biosphere_exists)

    def setup_file_menu(self) -> None:
        """Build the menu for specific importing/export/updating actions."""
        self.file_menu.addMenu(ProjectsMenu(self))
        self.file_menu.addAction(self.new_proj_action)
        self.file_menu.addAction(self.dup_proj_action)
        self.file_menu.addAction(self.delete_proj_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.import_proj_action)
        self.file_menu.addAction(self.export_proj_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.import_db_action)
        self.file_menu.addAction(self.export_db_action)
        self.file_menu.addAction(self.update_biosphere_action)
        self.file_menu.addSeparator()
        self.file_menu.addMenu(MigrationsMenu(self))
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.manage_settings_action)

    def setup_view_menu(self) -> None:
        """Build the menu for viewing or hiding specific tabs"""
        self.view_menu.addAction(
            qicons.graph_explorer,
            "&Graph Explorer",
            lambda: signals.toggle_show_or_hide_tab.emit("Graph Explorer"),
        )
        self.view_menu.addAction(
            qicons.history,
            "&Activity History",
            lambda: signals.toggle_show_or_hide_tab.emit("History"),
        )
        self.view_menu.addAction(
            qicons.welcome,
            "&Welcome screen",
            lambda: signals.toggle_show_or_hide_tab.emit("Welcome"),
        )

    def setup_tools_menu(self) -> None:
        """Build the tools menu for the menubar."""
        self.tools_menu.addAction(self.manage_plugins_action)

    def setup_help_menu(self) -> None:
        """Build the help menu for the menubar."""
        self.help_menu.addAction(
            self.window.icon, "&About Activity Browser", self.about
        )
        self.help_menu.addAction(
            "&About Qt", lambda: QtWidgets.QMessageBox.aboutQt(self.window)
        )
        self.help_menu.addAction(
            qicons.question, "&Get help on the wiki", self.open_wiki
        )
        self.help_menu.addAction(
            qicons.issue, "&Report an idea/issue on GitHub", self.raise_issue_github
        )

    def about(self):
        text = """
Activity Browser - a graphical interface for Brightway2.<br><br>
Application version: <b>{}</b><br><br>
All development happens on <a href="https://github.com/LCA-ActivityBrowser/activity-browser">github</a>.<br><br>
For copyright information please see the copyright on <a href="https://github.com/LCA-ActivityBrowser/activity-browser/tree/main#copyright">this page</a>.<br><br>
For license information please see the copyright on <a href="https://github.com/LCA-ActivityBrowser/activity-browser/blob/main/LICENSE.txt">this page</a>.<br><br>
"""
        msgBox = QtWidgets.QMessageBox(parent=self.window)
        msgBox.setWindowTitle("About the Activity Browser")
        pixmap = self.window.icon.pixmap(QSize(150, 150))
        msgBox.setIconPixmap(pixmap)
        msgBox.setWindowIcon(self.window.icon)
        msgBox.setText(text.format(ab_version))
        msgBox.exec_()

    def open_wiki(self):
        url = QUrl(
            "https://github.com/LCA-ActivityBrowser/activity-browser/wiki"
        )
        QtGui.QDesktopServices.openUrl(url)

    def raise_issue_github(self):
        url = QUrl(
            "https://github.com/LCA-ActivityBrowser/activity-browser/issues/new/choose"
        )
        QtGui.QDesktopServices.openUrl(url)

    @Slot(name="testBiosphereExists")
    def biosphere_exists(self) -> None:
        """Test if the default biosphere exists as a database in the project"""
        exists = True if bd.config.biosphere in bd.databases else False
        self.update_biosphere_action.setEnabled(exists)
        self.import_db_action.setEnabled(exists)


class ProjectsMenu(QtWidgets.QMenu):
    """
    Menu that lists all the projects available through bw2data.projects
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Open project")
        self.populate()

        self.aboutToShow.connect(self.populate)
        self.triggered.connect(lambda act: bd.projects.set_current(act.text()))

    def populate(self):
        """
        Populates the menu with the projects available in the database
        """
        import bw2data as bd

        # clear the menu of any already existing actions
        self.clear()

        # sort projects alphabetically
        sorted_projects = sorted(list(bd.projects))

        # iterate over the sorted projects and add them as actions to the menu
        for i, proj in enumerate(sorted_projects):
            # check whether the project is BW25
            bw_25 = (
                False if not isinstance(proj.data, dict) else proj.data.get("25", False)
            )

            # add BW25 decorations if necessary
            name = proj.name if not bw_25 or AB_BW25 else "[BW25] " + proj.name

            # create the action and disable it if it's BW25 and BW25 is not supported
            action = QtWidgets.QAction(name, self)
            action.setEnabled(not bw_25 or AB_BW25)

            self.addAction(action)


class MigrationsMenu(QtWidgets.QMenu):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setTitle("Migrations")
        self.install_migrations_action = actions.MigrationsInstall.get_QAction()

        self.addAction(self.install_migrations_action)

