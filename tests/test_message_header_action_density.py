from __future__ import annotations

import unittest
from pathlib import Path


class MessageHeaderActionDensityTests(unittest.TestCase):
    def test_detail_actions_use_individual_compact_controls(self) -> None:
        source = (Path(__file__).resolve().parents[1] / 'frontend-v2' / 'src' / 'pages' / 'Messages.tsx').read_text(encoding='utf-8')

        self.assertIn('flex items-center gap-1.5', source)
        self.assertNotIn('rounded-xl border border-border bg-surface p-1 shadow-sm', source)
        self.assertEqual(source.count('h-8 w-8 items-center justify-center rounded-[10px] border border-border-strong bg-surface'), 3)

        status_source = (Path(__file__).resolve().parents[1] / 'frontend-v2' / 'src' / 'components' / 'ui' / 'ConversationStatusSelect.tsx').read_text(encoding='utf-8')
        self.assertIn("'h-8 w-[176px] rounded-[10px] gap-1.5 text-sm'", status_source)


if __name__ == '__main__':
    unittest.main()
