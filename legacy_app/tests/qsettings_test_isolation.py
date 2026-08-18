"""Isolate PyQt QSettings writes from the user's real GUI settings."""

from __future__ import annotations

import unittest
import uuid

from PyQt5.QtCore import QSettings

from delete_test_qsettings_tree import delete_test_qsettings_tree


def use_isolated_qsettings(test_case: unittest.TestCase) -> None:
    import OCRLLM.gui.app as app_module
    import OCRLLM.gui.settings_dialog as settings_dialog_module
    import OCRLLM.gui.widgets as widgets_module
    from OCRLLM.gui.app import QCRMainWindow
    from OCRLLM.gui.widgets import PromptButton

    org = f"OCRLLMTests-{uuid.uuid4().hex}"
    app = "QCR"

    old_dialog_org = settings_dialog_module.SETTINGS_ORG
    old_dialog_app = settings_dialog_module.SETTINGS_APP
    old_main_org = QCRMainWindow._SETTINGS_ORG
    old_main_app = QCRMainWindow._SETTINGS_APP
    old_prompt_org = PromptButton._SETTINGS_ORG
    old_prompt_app = PromptButton._SETTINGS_APP

    settings_dialog_module.SETTINGS_ORG = org
    settings_dialog_module.SETTINGS_APP = app
    app_module.QCRMainWindow._SETTINGS_ORG = org
    app_module.QCRMainWindow._SETTINGS_APP = app
    widgets_module.PromptButton._SETTINGS_ORG = org
    widgets_module.PromptButton._SETTINGS_APP = app

    def restore() -> None:
        settings = QSettings(org, app)
        settings.clear()
        settings.sync()
        delete_test_qsettings_tree(org)
        settings_dialog_module.SETTINGS_ORG = old_dialog_org
        settings_dialog_module.SETTINGS_APP = old_dialog_app
        app_module.QCRMainWindow._SETTINGS_ORG = old_main_org
        app_module.QCRMainWindow._SETTINGS_APP = old_main_app
        widgets_module.PromptButton._SETTINGS_ORG = old_prompt_org
        widgets_module.PromptButton._SETTINGS_APP = old_prompt_app

    test_case.addCleanup(restore)
    settings = QSettings(org, app)
    settings.clear()
    settings.sync()


def isolated_settings() -> QSettings:
    import OCRLLM.gui.settings_dialog as settings_dialog_module

    return QSettings(settings_dialog_module.SETTINGS_ORG, settings_dialog_module.SETTINGS_APP)
