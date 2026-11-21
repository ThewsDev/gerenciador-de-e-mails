from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from src.screens.common import page_shell, add_bottom
from kivy.uix.widget import Widget
from src.ui.components import AppButton, AppLabel, CategoryChip, Surface
from src.config import settings


class CategoriesScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.box = BoxLayout(orientation="vertical")
        self.add_widget(self.box)

    def on_pre_enter(self, *args):
        self.box.clear_widgets()
        app = App.get_running_app()
        root = page_shell("Categorias", "Mensagens agrupadas automaticamente.")
        scroll = ScrollView()
        listing = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10))
        listing.bind(minimum_height=listing.setter("height"))
        for category, count in app.category_counts().items():
            card = Surface(size_hint_y=None, height=dp(64), padding=[dp(14), dp(10)], spacing=dp(8))
            card.add_widget(CategoryChip(category, pos_hint={"center_y": .5}))
            card.add_widget(Widget())
            card.add_widget(AppLabel(text=f"{count} e-mails", color=settings.COLORS["text_secondary"],
                                     font_size="12sp", size_hint_x=None, width=dp(78), halign="right"))
            btn = AppButton(text="Abrir", primary=True, size_hint_x=None, width=dp(72))
            btn.bind(on_release=lambda _, c=category: app.open_category(c))
            card.add_widget(btn)
            listing.add_widget(card)
        scroll.add_widget(listing)
        root.add_widget(scroll)
        add_bottom(root, "categories")
        self.box.add_widget(root)
