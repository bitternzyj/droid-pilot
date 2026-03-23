"""
pytest 配置和 fixtures
自动生成 by droid-pilot scaffold
"""
import os
import pytest
import subprocess

# droid-pilot skill 目录
SKILL_DIR = os.environ.get("DROID_PILOT_SKILL_DIR", "")
PACKAGE = "${PACKAGE}"


def pytest_configure(config):
    """设置环境变量"""
    if not os.environ.get("DROID_PILOT_SKILL_DIR"):
        # 尝试自动检测
        for candidate in [
            os.path.join(os.path.dirname(__file__), "..", ".claude", "skills", "droid-pilot"),
            os.path.join(os.path.dirname(__file__), ".claude", "skills", "droid-pilot"),
        ]:
            if os.path.isdir(candidate):
                os.environ["DROID_PILOT_SKILL_DIR"] = os.path.abspath(candidate)
                break


@pytest.fixture(scope="session")
def device():
    """获取设备 ID"""
    device_id = os.environ.get("DEVICE_ID", "")
    if not device_id:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        lines = [l for l in result.stdout.strip().split("\n")[1:] if l.strip() and "device" in l]
        if lines:
            device_id = lines[0].split("\t")[0]
    return device_id


@pytest.fixture(scope="session")
def package():
    """应用包名"""
    return PACKAGE


@pytest.fixture(autouse=True)
def restart_app(device, package):
    """每个测试前重启应用，保证隔离"""
    dev_args = ["-s", device] if device else []
    subprocess.run(["adb"] + dev_args + ["shell", "am", "force-stop", package],
                   capture_output=True, timeout=5)
    subprocess.run(["adb"] + dev_args + ["shell", "monkey", "-p", package,
                    "-c", "android.intent.category.LAUNCHER", "1"],
                   capture_output=True, timeout=5)
    import time
    time.sleep(2)  # 等待应用启动
    yield
    # teardown: 无需额外清理


${PAGE_FIXTURES}
