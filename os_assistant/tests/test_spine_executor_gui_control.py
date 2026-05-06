from queue import Queue

from agent.spine.executor import Executor


class FakeUIA:
    def __init__(self):
        self.clicked = []

    def get_active_window_info(self):
        return {"process_id": 1, "name": "Fake"}

    def click_element_by_name(self, name):
        self.clicked.append(name)
        return {"success": False, "error": "uia miss"}

    def type_element_by_name(self, name, text):
        return {"success": False, "error": "uia miss"}

    def get_text_from_focused(self):
        return ""

    def wait_for_element(self, name, timeout=5.0):
        return {"success": True, "name": name}

    def wait_for_window(self, query, timeout=8.0):
        return {"success": True, "window": {"name": query}}

    def get_window_summary(self):
        return "Window: WhatsApp | Labels: Payal, Message"


class FakeTargetCache:
    def find(self, query):
        return {"success": True, "center_x": 10, "center_y": 20}

    def summary(self):
        return ""

    def refresh(self, force=False):
        return {"success": True}


class FakeScreen:
    def get_screen_size(self):
        return 100, 100


class FakeInput:
    def click(self, x, y, button="left"):
        return {"success": True, "x": x, "y": y, "button": button}

    def type_text(self, text):
        return {"success": True, "text": text}


def test_smart_click_uses_target_cache_before_coordinates():
    executor = Executor(
        event_bus=Queue(),
        action_queue=Queue(),
        uia_helper=FakeUIA(),
        target_cache=FakeTargetCache(),
        gui_reliability=None,
        screen=FakeScreen(),
    )
    executor.input_adapter = FakeInput()

    result = executor._smart_click({"query": "Send", "x": 90, "y": 90})

    assert result["success"] is True
    assert result["x"] == 10
    assert result["y"] == 20
    methods = [step["method"] for step in result["fallback_chain"]]
    assert methods[:3] == ["uia_click", "target_cache", "target_cache_click"]
    assert "coordinate_last_fallback" not in methods


def test_coordinate_bounds_reject_out_of_screen_click():
    executor = Executor(
        event_bus=Queue(),
        action_queue=Queue(),
        uia_helper=FakeUIA(),
        target_cache=FakeTargetCache(),
        gui_reliability=None,
        screen=FakeScreen(),
    )

    result = executor._verify_coordinate_action({"action": "click", "x": 200, "y": 20})

    assert result["success"] is False
    assert "out of bounds" in result["error"]


def test_raw_click_with_query_is_rewritten_to_smart_click():
    executor = Executor(
        event_bus=Queue(),
        action_queue=Queue(),
        uia_helper=FakeUIA(),
        target_cache=FakeTargetCache(),
        gui_reliability=None,
        screen=FakeScreen(),
    )

    action = executor._normalize_action({"action": "click", "query": "Send", "x": 90, "y": 90})

    assert action["action"] == "smart_click"


def test_screenshot_coordinates_are_scaled_to_screen_space():
    executor = Executor(
        event_bus=Queue(),
        action_queue=Queue(),
        uia_helper=FakeUIA(),
        target_cache=FakeTargetCache(),
        gui_reliability=None,
        screen=FakeScreen(),
    )

    action = executor._normalize_action({
        "action": "click",
        "x": 50,
        "y": 25,
        "coordinate_space": "screenshot",
        "screenshot_width": 50,
        "screenshot_height": 50,
    })

    assert action["x"] == 100
    assert action["y"] == 50
    assert action["coordinate_space"] == "screen"


def test_verify_recipient_uses_current_ui_context():
    executor = Executor(
        event_bus=Queue(),
        action_queue=Queue(),
        uia_helper=FakeUIA(),
        target_cache=FakeTargetCache(),
        gui_reliability=None,
        screen=FakeScreen(),
    )

    result = executor._verify_recipient({"recipient": "Payal"})

    assert result["success"] is True
    assert result["recipient"] == "Payal"
