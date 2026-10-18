import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY", "")
if not GROQ_KEY:
    raise ValueError("GROQ_API_KEY is not set!")

client = AsyncOpenAI(
    api_key=GROQ_KEY,
    base_url="https://api.groq.com/openai/v1"
)


async def get_level_test_question(question_number: int) -> dict:
    prompt = f"""
    أنت مقيّم مستوى للغة الإنجليزية. اطرح سؤالاً واحداً فقط للمبتدئين.
    السؤال رقم {question_number} من 7. نوع السؤال: اختيار من متعدد.
    يجب أن يكون الرد بصيغة JSON فقط بالتنسيق التالي:
    {{
      "question": "نص السؤال",
      "options": ["خيار1", "خيار2", "خيار3", "خيار4"],
      "correct_index": 0
    }}
    """
    response = await client.chat.completions.create(
        model="openai/gpt-oss-120b",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You output JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return json.loads(response.choices[0].message.content)


async def get_lesson_content(level: str, topic: str) -> dict:
    prompt = f"""
    أنت معلم لغة إنجليزية. أنشئ درساً حول "{topic}" لمستوى {level}.
    يجب أن يحتوي الدرس على شرح موجز (3-4 أسطر)، مثال بالإنجليزية، وتمرين اختيار من متعدد.
    الرد بصيغة JSON فقط بالتنسيق:
    {{
      "lesson_explanation": "...",
      "example": "...",
      "exercise_question": "...",
      "exercise_options": ["...", "...", "...", "..."],
      "correct_index": 0
    }}
    """
    response = await client.chat.completions.create(
        model="openai/gpt-oss-120b",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You output JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return json.loads(response.choices[0].message.content)
