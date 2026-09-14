from __future__ import annotations

import unittest
from pathlib import Path


class EmailRendererFrameObserverTests(unittest.TestCase):
    def test_iframe_observers_are_constructed_in_the_email_document_realm(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "frontend-v2" / "src" / "components" / "EmailRenderer.tsx"
        ).read_text(encoding="utf-8")
        self.assertIn("doc.defaultView?.MutationObserver", source)
        self.assertIn("new FrameMutationObserver(updateHeight)", source)
        self.assertIn("doc.defaultView?.ResizeObserver", source)


if __name__ == "__main__":
    unittest.main()
