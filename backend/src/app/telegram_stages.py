from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic


DEFAULT_STAGE_TOTAL = 19
MIN_STAGE_EDIT_INTERVAL_SECONDS = 0.6


@dataclass(frozen=True)
class StageMessage:
    """Human-readable Telegram status for one backend pipeline stage."""

    key: str
    title: str
    details: str
    step: int | None = None
    total: int | None = DEFAULT_STAGE_TOTAL
    is_finalization: bool = False


STAGE_MESSAGES: dict[str, StageMessage] = {
    "start": StageMessage(
        key="start",
        title="Начинаю подбор техники...",
        details="Запускаю полный цикл /tech: разбор запроса, DNS-фильтры, парсинг, shortlist и финальный ответ.",
        step=None,
        total=None,
    ),
    "remember_mode": StageMessage(
        key="remember_mode",
        title="Запоминаем режим",
        details="Фиксирую, что запрос идёт через /tech, чтобы дальше использовать тех-цикл, память и parser.",
        step=1,
    ),
    "find_x": StageMessage(
        key="find_x",
        title="найди x",
        details="Выделяю предмет поиска из текста пользователя: что именно нужно найти в DNS.",
        step=2,
    ),
    "cycle_code_1_start": StageMessage(
        key="cycle_code_1_start",
        title="НАЧАЛО ЦИКЛА (КОД 1)",
        details="Запускаю основной цикл поиска: нормализация, фильтры, ссылка, parser, shortlist и финализация.",
        step=3,
    ),
    "bot1_category_brand": StageMessage(
        key="bot1_category_brand",
        title="бот 1 (категория, бренд)",
        details="Определяю категорию, бренд и базовый раздел DNS для дальнейшего поиска.",
        step=4,
    ),
    "bot2_price": StageMessage(
        key="bot2_price",
        title="бот 2 (цена)",
        details="Достаю бюджет и диапазон цены, чтобы не искать товары вне ограничения пользователя.",
        step=5,
    ),
    "bot4_wishes": StageMessage(
        key="bot4_wishes",
        title="бот 4 (пожелания)",
        details="Разделяю жёсткие требования и пожелания, чтобы не потерять смысл запроса при сборке фильтров.",
        step=6,
    ),
    "wait_bot3_notimeout": StageMessage(
        key="wait_bot3_notimeout",
        title="wait bot_3 notimeout",
        details="Жду готовности промежуточных данных перед сборкой общего JSON и характеристик.",
        step=7,
    ),
    "json_build_start": StageMessage(
        key="json_build_start",
        title="Сборка json",
        details="Собираю единый runtime_json: категория, цена, бренд, constraints, wishes и служебные поля.",
        step=8,
    ),
    "category_resolve_start": StageMessage(
        key="category_resolve_start",
        title="Определяю раздел DNS",
        details="Ищу подходящую категорию DNS, чтобы дальше брать реальные фильтры раздела.",
        step=9,
    ),
    "category_resolve_done": StageMessage(
        key="category_resolve_done",
        title="Раздел DNS найден",
        details="Категория определена. Дальше можно загрузить карту фильтров именно этого раздела.",
        step=10,
    ),
    "filters_map_start": StageMessage(
        key="filters_map_start",
        title="Загружаю карту фильтров DNS",
        details="Получаю filter_id, value_id и типы фильтров: checkbox, range и служебные параметры.",
        step=11,
    ),
    "filters_map_done": StageMessage(
        key="filters_map_done",
        title="Карта фильтров получена",
        details="Фильтры раздела готовы. Теперь можно сопоставлять требования пользователя с реальными параметрами DNS.",
        step=12,
    ),
    "filters_ai_start": StageMessage(
        key="filters_ai_start",
        title="Сопоставляю требования с реальными фильтрами",
        details="Проверяю, какие желания пользователя можно безопасно превратить в DNS-фильтры.",
        step=13,
    ),
    "filters_ai_done": StageMessage(
        key="filters_ai_done",
        title="Фильтры подготовлены",
        details="Набор фильтров собран. Следующий шаг — собрать корректную DNS-ссылку.",
        step=14,
    ),
    "filters_ai_skipped": StageMessage(
        key="filters_ai_skipped",
        title="Фильтры подготовлены",
        details="Дополнительный LLM-патч не понадобился: требования уже покрыты найденными фильтрами.",
        step=14,
    ),
    "create_link_start": StageMessage(
        key="create_link_start",
        title="составление ссылки",
        details="Перевожу runtime_json и выбранные фильтры в ссылку DNS.",
        step=15,
    ),
    "built_url_done": StageMessage(
        key="built_url_done",
        title="Собираю DNS-ссылку",
        details="Формирую URL из section_url, цены, города, наличия и реальных f/fr-параметров.",
        step=16,
    ),
    "parser_start": StageMessage(
        key="parser_start",
        title="Начинаю парс DNS",
        details="Открываю собранную ссылку и проверяю выдачу товаров.",
        step=17,
    ),
    "parser_done": StageMessage(
        key="parser_done",
        title="Товары получены",
        details="DNS-выдача разобрана. Дальше отбираю кандидатов для shortlist.",
        step=18,
    ),
    "shortlist_start": StageMessage(
        key="shortlist_start",
        title="Отбираю лучшие варианты",
        details="Убираю мусор и дубли, затем выбираю самые подходящие товары под запрос.",
        step=19,
    ),
    "shortlist_done": StageMessage(
        key="shortlist_done",
        title="Shortlist готов",
        details="Кандидаты выбраны. Теперь добираю характеристики для честного сравнения.",
        step=None,
        total=None,
    ),
    "bot3_characteristics": StageMessage(
        key="bot3_characteristics",
        title="бот 3 (характеристики)",
        details="Перехожу к характеристикам выбранных товаров, чтобы сравнение не строилось только по названию.",
        step=None,
        total=None,
    ),
    "details_start": StageMessage(
        key="details_start",
        title="Добираю характеристики",
        details="Собираю подробные параметры выбранных товаров: экран, память, процессор, функции и другие важные поля.",
        step=None,
        total=None,
    ),
    "details_done": StageMessage(
        key="details_done",
        title="Характеристики собраны",
        details="Факты по товарам готовы. Перехожу к финализации ответа.",
        step=None,
        total=None,
    ),
    "analysis_start": StageMessage(
        key="analysis_start",
        title="Финализация",
        details="Пишу итоговый ответ. На этом этапе включается stream DeepSeek, чтобы показать финальный текст по мере генерации.",
        step=None,
        total=None,
        is_finalization=True,
    ),
    "analysis_done": StageMessage(
        key="analysis_done",
        title="Финальный ответ готов",
        details="Проверяю формат и готовлю сообщение пользователю.",
        step=None,
        total=None,
        is_finalization=True,
    ),
    "render_done": StageMessage(
        key="render_done",
        title="Отправляю результат",
        details="Заменяю служебное сообщение финальным ответом.",
        step=None,
        total=None,
        is_finalization=True,
    ),
    "compare_link_start": StageMessage(
        key="compare_link_start",
        title="compare_link",
        details="Проверяю code товаров и готовлю compare-link для итогового сообщения.",
        step=None,
        total=None,
        is_finalization=True,
    ),
    "relax_start": StageMessage(
        key="relax_start",
        title="Товаров по точным фильтрам нет",
        details="Ослабляю самый безопасный фильтр, чтобы не завершать поиск слишком рано.",
        step=None,
        total=None,
    ),
    "relax_retry": StageMessage(
        key="relax_retry",
        title="Проверяю выдачу после ослабления",
        details="Пересобираю ссылку и снова проверяю количество товаров.",
        step=None,
        total=None,
    ),
    "relax_limit": StageMessage(
        key="relax_limit",
        title="Товары не найдены после нескольких попыток",
        details="Останавливаю retry-цикл и готовлю понятный fallback без технических деталей.",
        step=None,
        total=None,
    ),
}


def render_stage_message(stage_key: str) -> str:
    """Render a short stage message suitable for Telegram edit_text."""

    stage = STAGE_MESSAGES.get(stage_key)
    if stage is None:
        stage = StageMessage(
            key=stage_key,
            title="Продолжаю обработку запроса",
            details=f"Текущий внутренний этап: {stage_key}.",
            step=None,
            total=None,
        )
    if stage.step is not None and stage.total is not None:
        return f"Стадия {stage.step}/{stage.total}\n{stage.title}\n\nЧто делаю:\n{stage.details}"
    return f"{stage.title}\n\nЧто делаю:\n{stage.details}"


def looks_like_raw_json_chunk(chunk: str) -> bool:
    """Return True for chunks that should never be streamed to Telegram users."""

    stripped = chunk.strip()
    if not stripped:
        return False
    if stripped.startswith(("{", "[")):
        return True
    lowered = stripped.casefold()
    raw_markers = (
        '"selected_codes"',
        '"selected_urls"',
        '"filters"',
        '"filters_patch"',
        '"normalize_query"',
        '"intent_route"',
    )
    return any(marker in lowered for marker in raw_markers)


class TelegramStageReporter:
    """Async stage publisher driven by sync orchestrator stage callbacks."""

    def __init__(
        self,
        sent_message: object,
        state: dict[str, object],
        safe_edit_text: Callable[[object, str, dict[str, object]], Awaitable[str]],
        min_interval_seconds: float = MIN_STAGE_EDIT_INTERVAL_SECONDS,
    ) -> None:
        self.sent_message = sent_message
        self.state = state
        self.safe_edit_text = safe_edit_text
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self.finalization_started = False
        self._last_stage = ""
        self._last_edit_at = 0.0
        self._lock = asyncio.Lock()
        self._tasks: list[asyncio.Task[None]] = []

    def on_stage(self, stage_key: str) -> None:
        """Schedule a Telegram edit for a stage emitted by the orchestrator."""

        if stage_key == self._last_stage:
            return
        self._last_stage = stage_key
        if stage_key == "analysis_start":
            self.finalization_started = True
        task = asyncio.create_task(self._publish(stage_key))
        self._tasks.append(task)

    async def flush(self) -> None:
        """Wait until all scheduled stage edits are done."""

        if not self._tasks:
            return
        tasks = list(self._tasks)
        self._tasks.clear()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _publish(self, stage_key: str) -> None:
        async with self._lock:
            elapsed = monotonic() - self._last_edit_at
            if self._last_edit_at and elapsed < self.min_interval_seconds:
                await asyncio.sleep(self.min_interval_seconds - elapsed)
            await self.safe_edit_text(self.sent_message, render_stage_message(stage_key), self.state)
            self._last_edit_at = monotonic()
