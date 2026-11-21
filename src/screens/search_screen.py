from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from src.database.database import MessageQuery
from src.screens.common import page_shell, add_bottom, fill_list
from src.ui.components import SearchField, EmailItem, AppLabel
from src.ui.components import AppButton
from src.utils.dates import now_ms
from src.config import settings

_DEBOUNCE_SECONDS = 0.25
_DAY_MS = 86_400_000
_PERIODS = [("Tudo", None), ("7 dias", 7), ("30 dias", 30)]


class SearchScreen(Screen):
    """Pesquisa no SQLite: texto (remetente, assunto, conteúdo) + categoria + período."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.box = BoxLayout(orientation="vertical")
        self.add_widget(self.box)
        self._pending = None
        self.category = None
        self.days = None

    def on_pre_enter(self, *args):
        self.box.clear_widgets()
        root = page_shell("Pesquisar", "Busque por remetente, assunto ou conteúdo.")
        self.field = SearchField()
        self.field.bind(text=lambda *_: self._schedule_update())
        root.add_widget(self.field)
        self.results = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.results.bind(minimum_height=self.results.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self.results)
        root.add_widget(scroll)
        self.update_results()
        add_bottom(root, "search")
        self.box.add_widget(root)

    def on_leave(self, *args):
        if self._pending:
            self._pending.cancel()
            self._pending = None

    def _schedule_update(self):
        # Evita uma consulta a cada tecla digitada.
        if self._pending:
            self._pending.cancel()
        self._pending = Clock.schedule_once(lambda _dt: self.update_results(), _DEBOUNCE_SECONDS)

    def update_results(self):
        self._pending = None
        self.results.clear_widgets()
        app = App.get_running_app()
        text = self.field.text.strip()
        since = now_ms() - self.days * _DAY_MS if self.days else None
        matches = app.query_messages(MessageQuery(text=text, category=self.category,
                                                  date_from_ms=since))
        if not matches:
            self.results.add_widget(AppLabel(text="Nenhum e-mail encontrado.",
                                             color=settings.COLORS["text_secondary"],
                                             size_hint_y=None, height=dp(42)))
        fill_list(self.results, matches, app.open_message)
