"""共享的 pytest fixture。"""
import pytest


@pytest.fixture(scope="session")
def qapp():
    """整个测试会话共用一个 QApplication —— Qt 不允许同时存在多个实例。"""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
