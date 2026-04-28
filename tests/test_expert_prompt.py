import unittest

from tools.expert_prompt import render_expert_prompt


class ExpertPromptTests(unittest.TestCase):
    def test_render_prompt(self) -> None:
        output = render_expert_prompt(
            non_engineer_logic="優先推薦湯頭評價高的店",
            user_query="走路 20 分鐘內，韓式，評價高，有豆腐鍋",
        )
        self.assertIn("優先推薦湯頭評價高的店", output)
        self.assertIn("走路 20 分鐘內，韓式，評價高，有豆腐鍋", output)
        self.assertIn("步行距離 <= 20 分鐘", output)


if __name__ == "__main__":
    unittest.main()
