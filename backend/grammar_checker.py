import re
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()


class GrammarChecker:


    def __init__(self):

        try:
            import language_tool_python
            self.tool = language_tool_python.LanguageTool('ru')
            self.enabled = True
            logger.info("language_tool_initialized")
        except Exception as e:
            logger.warning("language_tool_not_available", error=str(e))
            self.enabled = False

    def check(self, text: str, max_issues: int = 20) -> Dict[str, Any]:

        if not self.enabled:
            return {
                "status": "disabled",
                "message": "LanguageTool недоступен. Установите language-tool-python.",
                "issues": []
            }

        if not text or len(text.strip()) < 10:
            return {"status": "empty", "issues": []}


        if len(text) > 10000:
            text = text[:10000]

        try:
            matches = self.tool.check(text)

            issues = []
            for match in matches[:max_issues]:
                issues.append({
                    "type": match.ruleId,
                    "category": match.category,
                    "message": match.message,
                    "context": text[max(0, match.offset - 30):match.offset + match.errorLength + 30],
                    "suggestions": match.replacements[:3],
                    "offset": match.offset,
                    "length": match.errorLength
                })

            # Статистика по категориям
            categories = {}
            for issue in issues:
                cat = issue["category"]
                categories[cat] = categories.get(cat, 0) + 1

            return {
                "status": "success",
                "total_issues": len(matches),
                "shown_issues": len(issues),
                "categories": categories,
                "issues": issues,
                "text_length": len(text)
            }

        except Exception as e:
            logger.error("grammar_check_failed", error=str(e))
            return {
                "status": "error",
                "message": str(e),
                "issues": []
            }

    def check_style(self, text: str) -> Dict[str, Any]:

        issues = []


        канцеляризмы = [
            (r'\bв связи с тем что\b', "в связи с тем что", "потому что"),
            (r'\bв случае если\b', "в случае если", "если"),
            (r'\bв целях\b', "в целях", "для"),
            (r'\bс целью\b', "с целью", "для"),
            (r'\bв рамках\b', "в рамках", "в"),
            (r'\bпосредством\b', "посредством", "с помощью"),
            (r'\bвышеуказанный\b', "вышеуказанный", "этот/тот"),
            (r'\bнижеподписавшийся\b', "нижеподписавшийся", "я"),
        ]

        for pattern, bad, good in канцеляризмы:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                issues.append({
                    "type": "style",
                    "category": "канцеляризм",
                    "message": f"Канцеляризм '{bad}' лучше заменить на '{good}'",
                    "context": self._get_context(text, match.start(), match.end()),
                    "suggestions": [good]
                })


        пассив = r'\b(был|была|было|были)\s+\w+нн?о\b'
        for match in re.finditer(пассив, text):
            issues.append({
                "type": "style",
                "category": "пассив",
                "message": "Пассивная конструкция снижает читаемость",
                "context": self._get_context(text, match.start(), match.end()),
                "suggestions": ["Переформулируйте в активный залог"]
            })


        предложения = re.split(r'[.!?]+', text)
        for предложение in предложения:
            слова = предложение.strip().split()
            if len(слова) > 25:
                issues.append({
                    "type": "style",
                    "category": "длинное_предложение",
                    "message": f"Предложение слишком длинное ({len(слова)} слов). Разбейте на несколько.",
                    "context": предложение[:200] + "..." if len(предложение) > 200 else предложение,
                    "suggestions": ["Разбейте на 2-3 предложения"]
                })


        статистика = {
            "канцеляризмы": len([i for i in issues if i["category"] == "канцеляризм"]),
            "пассив": len([i for i in issues if i["category"] == "пассив"]),
            "длинные_предложения": len([i for i in issues if i["category"] == "длинное_предложение"])
        }

        return {
            "total_issues": len(issues),
            "statistics": статистика,
            "issues": issues[:20],
            "recommendations": self._generate_style_recommendations(статистика)
        }

    def _get_context(self, text: str, start: int, end: int, window: int = 30) -> str:

        контекст_start = max(0, start - window)
        контекст_end = min(len(text), end + window)
        return text[контекст_start:контекст_end]

    def _generate_style_recommendations(self, stats: Dict[str, int]) -> List[str]:

        рекомендации = []

        if stats.get("канцеляризмы", 0) > 3:
            рекомендации.append("Уменьшите количество канцеляризмов для улучшения читаемости")

        if stats.get("пассив", 0) > 2:
            рекомендации.append("Замените пассивные конструкции на активные")

        if stats.get("длинные_предложения", 0) > 3:
            рекомендации.append("Разбейте длинные предложения на более короткие")

        if not рекомендации:
            рекомендации.append("Стиль текста хороший, замечаний нет")

        return рекомендации