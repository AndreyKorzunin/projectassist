import re
from typing import List, Dict, Any
from collections import Counter
import structlog

logger = structlog.get_logger()


class TextAnalyzer:


    def find_repetitions(self, text: str, threshold: float = 0.85, min_length: int = 5) -> Dict[str, Any]:



        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > min_length]


        sentence_counts = Counter(sentences)
        duplicates = [
            {"text": sent, "count": count}
            for sent, count in sentence_counts.items()
            if count > 1
        ]


        common_words = self._find_common_words(text)

        return {
            "exact_duplicates": sorted(duplicates, key=lambda x: x["count"], reverse=True)[:10],
            "common_words": common_words[:20],
            "total_sentences": len(sentences),
            "unique_sentences": len(set(sentences)),
            "redundancy_score": 1 - (len(set(sentences)) / len(sentences)) if sentences else 0
        }

    def _find_common_words(self, text: str) -> List[Dict[str, Any]]:


        stop_words = {
            'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то',
            'все', 'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за',
            'бы', 'по', 'только', 'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще',
            'нет', 'о', 'из', 'ему', 'теперь', 'когда', 'даже', 'ну', 'вдруг', 'ли',
            'если', 'уже', 'или', 'ни', 'быть', 'был', 'него', 'до', 'вас', 'нибудь',
            'опять', 'уж', 'вам', 'сказал', 'ведь', 'там', 'потом', 'себя', 'ничего',
            'ей', 'может', 'они', 'тут', 'где', 'есть', 'надо', 'ней', 'для', 'мы',
            'тебя', 'их', 'чем', 'была', 'сам', 'чтоб', 'без', 'будто', 'человек',
            'чего', 'раз', 'тоже', 'себе', 'под', 'жизнь', 'будет', 'ж', 'тогда',
            'кто', 'этот', 'говорил', 'того', 'потому', 'этого', 'какой', 'совсем',
            'ним', 'здесь', 'этом', 'один', 'почти', 'мой', 'тем', 'чтобы', 'нее',
            'кажется', 'сейчас', 'были', 'куда', 'зачем', 'сказать', 'всех', 'никогда',
            'сегодня', 'можно', 'при', 'наконец', 'два', 'об', 'другой', 'хоть',
            'после', 'над', 'больше', 'тот', 'через', 'эти', 'нас', 'про', 'всего',
            'них', 'какая', 'много', 'разве', 'сказала', 'три', 'эту', 'моя',
            'впрочем', 'хорошо', 'свою', 'этой', 'перед', 'иногда', 'лучше', 'чуть',
            'том', 'нельзя', 'такой', 'им', 'более', 'всегда', 'конечно', 'всю',
            'между', 'это', 'на', 'по', 'к', 'из', 'от', 'до', 'без', 'над', 'под',
            'для', 'перед', 'через', 'после', 'около', 'возле', 'вокруг', 'среди'
        }


        words = re.findall(r'\b[а-яё]{3,}\b', text.lower())
        words = [w for w in words if w not in stop_words]

        word_counts = Counter(words)

        return [
            {"word": word, "count": count, "frequency": count / len(words) if words else 0}
            for word, count in word_counts.most_common(50)
        ]

    def analyze_structure(self, content: Dict[str, Any]) -> Dict[str, Any]:

        doc_type = content.get("metadata", {}).get("type")

        if doc_type == "word":
            return self._analyze_word_structure(content)
        elif doc_type == "excel":
            return self._analyze_excel_structure(content)
        else:
            return {"error": "Unsupported document type"}

    def _analyze_word_structure(self, content: Dict[str, Any]) -> Dict[str, Any]:

        headings = content.get("headings", [])
        paragraphs = content.get("paragraphs", [])
        tables = content.get("tables", [])
        lists = content.get("lists", [])


        heading_levels = {}
        for h in headings:
            level = h["level"]
            heading_levels[level] = heading_levels.get(level, 0) + 1


        main_sections = [
            {"level": h["level"], "text": h["text"][:100], "position": h["index"]}
            for h in headings if h["level"] <= 2
        ]


        avg_paragraph_length = (
            sum(len(p.split()) for p in paragraphs) / len(paragraphs)
            if paragraphs else 0
        )

        return {
            "document_type": "Word",
            "headings": {
                "total": len(headings),
                "by_level": heading_levels,
                "main_sections": main_sections[:10]
            },
            "content": {
                "paragraphs_count": len(paragraphs),
                "avg_paragraph_length": round(avg_paragraph_length, 1),
                "tables_count": len(tables),
                "lists_count": len(lists)
            },
            "structure_quality": self._assess_structure_quality(headings, paragraphs, tables),
            "recommendations": self._generate_structure_recommendations(headings, paragraphs, tables)
        }

    def _analyze_excel_structure(self, content: Dict[str, Any]) -> Dict[str, Any]:

        sheets = content.get("sheets", {})

        sheets_analysis = {}
        for sheet_name, sheet_data in sheets.items():
            sheets_analysis[sheet_name] = {
                "rows": sheet_data["rows"],
                "cols": sheet_data["cols"],
                "has_headers": sheet_data["headers"] is not None,
                "numeric_columns": len(sheet_data["numeric_columns"]),
                "data_density": sheet_data["rows"] * sheet_data["cols"]
            }

        return {
            "document_type": "Excel",
            "sheets_count": len(sheets),
            "sheets": sheets_analysis,
            "total_rows": sum(s["rows"] for s in sheets.values()),
            "recommendations": self._generate_excel_recommendations(sheets)
        }

    def _assess_structure_quality(self, headings, paragraphs, tables) -> Dict[str, Any]:

        score = 100

        if not headings:
            score -= 30
        elif len([h for h in headings if h["level"] == 1]) < 2:
            score -= 15

        if not paragraphs:
            score -= 20

        if tables:
            score += 5

        score = max(0, min(100, score))

        quality = "Отличная" if score >= 80 else "Хорошая" if score >= 60 else "Удовлетворительная" if score >= 40 else "Слабая"

        return {
            "score": score,
            "quality": quality,
            "factors": {
                "has_headings": len(headings) > 0,
                "has_content": len(paragraphs) > 0,
                "content_to_headings_ratio": len(paragraphs) / len(headings) if headings else 0
            }
        }

    def _generate_structure_recommendations(self, headings, paragraphs, tables) -> List[str]:

        recommendations = []

        if not headings:
            recommendations.append("Добавьте заголовки для структурирования документа")
        elif len([h for h in headings if h["level"] == 1]) < 2:
            recommendations.append("Добавьте больше основных разделов (заголовки уровня 1)")

        if len(paragraphs) > 50 and len(headings) < 5:
            recommendations.append("Разбейте большой объём текста на больше разделов")

        avg_paragraph_length = sum(len(p.split()) for p in paragraphs) / len(paragraphs) if paragraphs else 0
        if avg_paragraph_length > 100:
            recommendations.append("Сократите длинные абзацы (рекомендуется до 100 слов)")

        return recommendations

    def _generate_excel_recommendations(self, sheets) -> List[str]:

        recommendations = []

        if len(sheets) > 10:
            recommendations.append("Рассмотрите объединение листов с похожими данными")

        for sheet_name, sheet_data in sheets.items():
            if not sheet_data.get("headers"):
                recommendations.append(f"Добавьте заголовки на лист '{sheet_name}'")

            density = sheet_data["rows"] * sheet_data["cols"]
            if density > 10000:
                recommendations.append(f"Лист '{sheet_name}' содержит много данных — рассмотрите разбиение")

        return recommendations