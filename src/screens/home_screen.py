from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import Screen
from src.screens.common import page_shell, add_bottom
from src.ui.components import AppLabel, EmailItem, Icon, Surface
from src.config import settings


class _LinkLabel(ButtonBehavior, AppLabel):
    pass


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root_box = BoxLayout(orientation="vertical")
        self.add_widget(self.root_box)

    def on_pre_enter(self, *args):
        self.root_box.clear_widgets()
        app = App.get_running_app()
        secondary = settings.COLORS["text_secondary"]
        root = page_shell("Seus e-mails.", "Sua caixa de entrada organizada.",
                          big=True, show_refresh=True)

        # Cartões de resumo
        stats = BoxLayout(size_hint_y=None, height=dp(104), spacing=dp(10))
        for icon, color, value, label in [
                ("inbox", "#60A5FA", str(app.count_messages()), "Mensagens"),
                ("folder-check", "#34D399", str(len(settings.CATEGORIES)), "Categorias")]:
            card = Surface(orientation="vertical", padding=[dp(14), dp(10)], spacing=dp(2))
            card.add_widget(Icon(icon, color=color, size=18, halign="left",
                                 size_hint_y=None, height=dp(26)))
            card.add_widget(AppLabel(text=value, font_size="20sp", bold=True))
            card.add_widget(AppLabel(text=label, color=secondary, font_size="10sp",
                                     size_hint_y=None, height=dp(18)))
            stats.add_widget(card)
        root.add_widget(stats)

        # Mensagens recentes
        head = BoxLayout(size_hint_y=None, height=dp(26))
        head.add_widget(AppLabel(text="Mensagens recentes", bold=True, font_size="14sp"))
        all_btn = _LinkLabel(text="Ver todos", color=settings.COLORS["primary"], font_size="11sp",
                             halign="right", size_hint_x=None, width=dp(80))
        all_btn.bind(on_release=lambda *_: app.navigate("inbox"))
        head.add_widget(all_btn)
        root.add_widget(head)

        scroll = ScrollView(bar_width=0)
        items = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        items.bind(minimum_height=items.setter("height"))
        recent = app.query_messages(limit=5)
        for email in recent:
            items.add_widget(EmailItem(email, on_press=app.open_message))
        if not recent:
            items.add_widget(AppLabel(text="Nenhuma mensagem armazenada ainda.", color=secondary,
                                      size_hint_y=None, height=dp(44)))
        scroll.add_widget(items)
        root.add_widget(scroll)
        add_bottom(root, "home")
        self.root_box.add_widget(root)
