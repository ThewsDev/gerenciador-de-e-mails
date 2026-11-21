from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from src.screens.common import page_shell, add_bottom
from src.ui.components import AppLabel, AppButton, Surface
from src.ui.formatting import format_size
from src.config import settings


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.box = BoxLayout(orientation="vertical")
        self.add_widget(self.box)

    def on_pre_enter(self, *args):
        self.box.clear_widgets()
        app = App.get_running_app()
        root = page_shell("Configurações", "Conta e preferências do aplicativo.")
        secondary = settings.COLORS["text_secondary"]

        account = Surface(orientation="vertical", size_hint_y=None, height=dp(148),
                          padding=dp(14), spacing=dp(7))
        account.add_widget(AppLabel(text="Conta Gmail", bold=True, font_size="16sp"))
        if app.gmail_authorized:
            account.add_widget(AppLabel(text="Conectada: " + (app.account_email or "Google"),
                                        color="#22C55E"))
            account.add_widget(AppLabel(text="Permissão somente leitura (gmail.readonly).",
                                        color=secondary, font_size="11sp"))
            action = AppButton(text="Desconectar conta", size_hint_y=None, height=dp(42))
            action.bind(on_release=lambda *_: app.confirm(
                "Desconectar a conta e apagar os e-mails deste aparelho?",
                app.disconnect_gmail, confirm_text="Desconectar"))
        else:
            account.add_widget(AppLabel(text="Não conectada", color=secondary))
            account.add_widget(AppLabel(
                text="A autorização será realizada pelo Google Play Services.",
                color=secondary, font_size="11sp"))
            action = AppButton(text="Conectar conta Google", primary=True,
                               size_hint_y=None, height=dp(42))
            action.bind(on_release=lambda *_: app.connect_gmail(choose_account=True))
        account.add_widget(action)
        root.add_widget(account)

        total = app.count_messages()
        size = app._db_call(app.db.size_bytes, 0) if total else 0
        local = Surface(orientation="vertical", size_hint_y=None, height=dp(84),
                        padding=dp(14), spacing=dp(5))
        local.add_widget(AppLabel(text="Banco de dados local", bold=True, font_size="16sp"))
        local.add_widget(AppLabel(text=f"{total} e-mails · {format_size(size)}", color=secondary))
        root.add_widget(local)

        clear = AppButton(text="Apagar e-mails armazenados", size_hint_y=None, height=dp(46))
        clear.bind(on_release=lambda *_: app.confirm(
            "Apagar todos os e-mails salvos neste dispositivo?\n"
            "Os e-mails na sua conta Gmail não são afetados.",
            lambda: self._clear(app), confirm_text="Apagar"))
        root.add_widget(clear)

        info = Surface(orientation="vertical", size_hint_y=None, height=dp(100),
                       padding=dp(14), spacing=dp(5))
        info.add_widget(AppLabel(text=settings.APP_NAME, bold=True))
        info.add_widget(AppLabel(text=f"Versão {settings.APP_VERSION} · Dark Mode", color=secondary))
        info.add_widget(AppLabel(text="Seus dados são armazenados localmente no dispositivo.",
                                 color=secondary, font_size="11sp"))
        root.add_widget(info)
        root.add_widget(Widget())
        add_bottom(root, "settings")
        self.box.add_widget(root)

    def _clear(self, app):
        app._db_call(app.db.clear_messages, 0)
        self.on_pre_enter()
