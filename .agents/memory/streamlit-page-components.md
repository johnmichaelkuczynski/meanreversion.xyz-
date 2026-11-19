---
name: Streamlit multipage component registration
description: Declare iframe components from importable modules, not directly from page scripts.
---

Keep custom iframe component declarations in imported Python modules when using
Streamlit's multipage navigation.

**Why:** A page script's execution namespace may not be registered in Python's
module table. Streamlit inspects the declaration's caller and can raise
`RuntimeError: module is None` when the same declaration worked as the entry script.

**How to apply:** Put the declaration in an imported helper and call that helper
from the page. Verify the actual page route, not only the default landing page.
