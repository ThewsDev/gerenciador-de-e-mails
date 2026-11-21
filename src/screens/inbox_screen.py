from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from src.database.database import MessageQuery
from src.screens.common import page_shell, add_bottom, fill_list
from src.ui.components import EmailItem, AppLabel
from src.config import settings


class InboxScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.box = BoxLayout(orientation="vertical")
        self.add_widget(self.box)

    def on_pre_enter(self, *args):
        self.box.clear_widgets()
        app = App.get_running_app()
        query = MessageQuery(category=app.category_filter)
        total = app.count_messages(query)
        emails = app.query_messages(query)
        if app.category_filter:
            subtitle = f"Categoria: {app.category_filter} · {total} mensagens"
        else:
            subtitle = f"{total} mensagens"
        if total > len(emails):
            subtitle += f" (exibindo as {len(emails)} mais recentes)"
        root = page_shell("Caixa de entrada", subtitle)
        scroll = ScrollView()
        listing = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(9))
        listing.bind(minimum_height=listing.setter("height"))
        fill_list(listing, emails, app.open_message)
        if not emails:
            text = ("Nenhuma mensagem nesta categoria." if app.category_filter
                    else "Nenhuma mensagem armazenada ainda.")
            listing.add_widget(AppLabel(text=text, color=settings.COLORS["text_secondary"],
                                        size_hint_y=None, height=dp(44)))
        scroll.add_widget(listing)
        root.add_widget(scroll)
        add_bottom(root, "")
        self.box.add_widget(root)
