"""Revert runner.py NEMO loop to use self._close_tab etc. wrappers."""
from pathlib import Path

p = Path("survey-cli/survey/runner.py")
text = p.read_text()

# Revert opener.close(target) back to self._close_tab(tab_id) in the NEMO loop
# But keep the opening block using opener.

# Replace opener.close(target) with self._close_tab(tab_id)
text = text.replace("opener.close(target)", "self._close_tab(tab_id)")

# Replace opener.refresh_ws(target) with self._refresh_tab_ws(tab_id)
text = text.replace("tab_ws_current = opener.refresh_ws(target)", "tab_ws_current = self._refresh_tab_ws(tab_id)")

p.write_text(text)
print("Done")
