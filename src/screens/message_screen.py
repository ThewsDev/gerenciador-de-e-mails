from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from src.ui.components import AppLabel, IconButton, CategoryPill, Surface
from src.config import settings


class MessageScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        self.add_widget(self.box)

    def on_pre_enter(self, *args):
        self.box.clear_widgets()
        app = App.get_running_app()
        email = app.get_message_view(app.selected_message_id) or {}
        if email and not email.get("is_read", True):
            app._db_call(app.db.mark_read, None, app.selected_message_id)
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        back = IconButton("back", size=22, color=settings.COLORS["text"], size_hint_x=None, width=dp(40))
        back.bind(on_release=lambda *_: app.close_message())
        top.add_widget(back)
        top.add_widget(AppLabel(text="Mensagem", bold=True, font_size="17sp"))
        self.box.add_widget(top)
        self.box.add_widget(AppLabel(text=email.get("subject", "(Sem assunto)"),
                                     bold=True, font_size="22sp", size_hint_y=None, height=dp(64)))
        meta = Surface(orientation="vertical", size_hint_y=None, height=dp(88),
                       padding=dp(12), spacing=dp(4))
        meta.add_widget(AppLabel(text=email.get("sender", ""), bold=True))
        meta.add_widget(AppLabel(text=email.get("date_full", ""), color=settings.COLORS["text_secondary"],
                                 font_size="12sp"))
        meta.add_widget(CategoryPill(email.get("category", "Outros")))
        self.box.add_widget(meta)
        scroll = ScrollView()
        body = AppLabel(text=(email.get("body") or email.get("preview")
                             or ("Sem conteúdo disponível." if email else "Mensagem não encontrada.")),
                        color=settings.COLORS["text"], font_size="14sp", valign="top")
        body.size_hint_y = None
        body.bind(width=lambda inst, width: setattr(inst, "text_size", (width, None)))
        body.bind(texture_size=lambda inst, size: setattr(inst, "height", size[1] + dp(16)))
        scroll.add_widget(body)
        self.box.add_widget(scroll)
        self.box.add_widget(AppLabel(text="Modo de leitura · Somente visualização",
                                     color=settings.COLORS["text_secondary"], font_size="11sp",
                                     size_hint_y=None, height=dp(28)))
