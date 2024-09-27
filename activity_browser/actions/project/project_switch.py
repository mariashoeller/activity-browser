from logging import getLogger

from activity_browser.actions.base import ABAction, exception_dialogs
from activity_browser.mod import bw2data as bd

log = getLogger(__name__)


class ProjectSwitch(ABAction):
    """
    ABAction to switch to another project.
    """

    text = "Switch project"
    tool_tip = "Switch the project"

    @staticmethod
    @exception_dialogs
    def run(project_name: str):
        
        if not project_name == bd.projects.current:
            bd.projects.set_current(project_name)
            log.info(f"Brightway2 current project: {project_name}")
        else:
            log.info(f"Brightway2 already selected: {project_name}")
