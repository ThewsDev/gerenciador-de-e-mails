"""Ponto de entrada do Email Manager: inicializa o banco, a navegação e as telas."""
import logging
import sqlite3
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.utils import get_color_from_hex

from src.config import settings
from src.database.database import Database, MessageQuery
from src.screens.home_screen import HomeScreen
from src.screens.inbox_screen import InboxScreen
from src.screens.categories_screen import CategoriesScreen
from src.screens.search_screen import SearchScreen
from src.screens.settings_screen import SettingsScreen
from src.screens.message_screen import MessageScreen
from src.ui.components import AppButton
from src.ui.formatting import to_view_model

log = logging.getLogger("email_manager")



class EmailManagerApp(App):
    title = settings.APP_NAME

    def build(self):
        Window.clearcolor = get_color_from_hex(settings.COLORS["background"])
        # O banco precisa existir antes das telas: user_data_dir é o armazenamento
        # privado do app no Android.
        settings.ensure_data_dir(self.user_data_dir)
        self.db = Database(settings.db_path())
        self.db.initialize()

        self.token_store = None
        self.google_auth = None
        self.gmail_authorized = False
        accounts = self._db_call(self.db.list_accounts, [])
        self.account_email = accounts[0]["email"] if accounts else None
        self._syncing = False
        self._sync_after_auth = False
        self._auth_retried = False
        self._progress_label = None
        self._progress_popup = None

        self.selected_message_id = None
        self.message_origin = "inbox"
        self.category_filter = None
        self.sm = ScreenManager(transition=FadeTransition(duration=.12))
        for screen in [HomeScreen(name="home"), InboxScreen(name="inbox"),
                       CategoriesScreen(name="categories"), SearchScreen(name="search"),
                       SettingsScreen(name="settings"), MessageScreen(name="message")]:
            self.sm.add_widget(screen)
        self.sm.current = "home"
        return self.sm

    # ------------------------------------------------------------- navegação
    def on_pause(self):
        return True  # sem isso o Android encerra o app ao abrir o seletor de contas

    def on_resume(self):
        pass

    def navigate(self, route):
        if route in self.sm.screen_names:
            self.category_filter = None
            self.sm.current = route

    def open_category(self, category):
        self.category_filter = category
        self.sm.current = "inbox"

    def open_message(self, email):
        self.selected_message_id = email["id"]
        self.message_origin = self.sm.current
        self.sm.current = "message"

    def close_message(self):
        """Volta para a tela de onde a mensagem foi aberta (mantém o filtro de categoria)."""
        self.sm.current = self.message_origin

    # --------------------------------------------- acesso ao banco para as telas
    def _db_call(self, func, default, *args, **kwargs):
        """Executa uma consulta; erros de SQLite são registrados e avisados, nunca silenciosos."""
        try:
            return func(*args, **kwargs)
        except sqlite3.Error:
            log.exception("Falha ao acessar o banco local")
            self.show_notice("Não foi possível acessar o banco de dados local.")
            return default

    def query_messages(self, query=None, limit=settings.LIST_PAGE_SIZE):
        rows = self._db_call(self.db.search, [], query or MessageQuery(), limit=limit)
        return [to_view_model(row) for row in rows]

    def count_messages(self, query=None):
        return self._db_call(self.db.count, 0, query or MessageQuery())

    def category_counts(self):
        counts = self._db_call(self.db.count_by_category, {})
        return {category: counts.get(category, 0) for category in settings.CATEGORIES}

    def get_message_view(self, message_id):
        row = self._db_call(self.db.get_message, None, message_id)
        return to_view_model(row) if row else None


    # ------------------------------------------------------ autorização Google
    def connect_gmail(self, choose_account=False):
        """Inicia a autorização nativa (Google Play Services); o token fica só em memória."""
        from kivy.utils import platform
        if platform != "android":
            self.show_notice("A conexão Gmail está disponível somente no aplicativo Android.")
            return
        try:
            from src.services.token_store import TokenStore
            from src.auth.google_auth import GoogleAuth
            if self.token_store is None:
                self.token_store = TokenStore()
            if self.google_auth is None:
                self.google_auth = GoogleAuth(
                    self.token_store,
                    on_authorized=self._on_gmail_authorized,
                    on_error=self._on_gmail_auth_error,
                )
            if choose_account:
                self.google_auth.pick_account()  # usuário escolhe qual conta conectar
            else:
                self.google_auth.authorize(self.account_email)  # mantém a conta atual
        except Exception:
            log.exception("Não foi possível preparar a autorização Gmail")
            self._sync_after_auth = False
            self._finish_sync_ui()
            self.show_notice("Não foi possível acessar a sua conta. Conecte novamente.")

    def _on_gmail_authorized(self):
        self.gmail_authorized = True
        log.info("Permissão gmail.readonly concedida")
        self._refresh_current_screen()
        if self._sync_after_auth:
            self._sync_after_auth = False
            self._start_sync()
        else:
            self.sync()  # primeira conexão: já traz os e-mails

    def _on_gmail_auth_error(self, message):
        self._sync_after_auth = False
        self._finish_sync_ui()
        self.show_notice(message)

    def disconnect_gmail(self):
        """Desconecta neste aparelho: descarta o token e apaga a conta e os e-mails locais.

        Não revoga no servidor do Google: isso deixaria o Play Services com um token
        em cache já inválido e quebraria a reconexão. O acesso completo pode ser
        removido em myaccount.google.com/permissions.
        """
        if self.token_store:
            self.token_store.clear()
        self._forget_account()
        self.show_notice("Conta desconectada e e-mails apagados deste aparelho.")
        self.navigate("settings")
        self._refresh_current_screen()  # já estando em Configurações, reconstrói a tela

    def _forget_account(self):
        """Ao desconectar, apaga também a conta e os e-mails locais (privacidade)."""
        self.gmail_authorized = False
        if self.account_email:
            self._db_call(self.db.remove_account, 0, self.account_email)
            self.account_email = None

    # -------------------------------------------------------- sincronização
    def sync(self):
        """Botão Atualizar: garante autorização e sincroniza em segundo plano (thread)."""
        from kivy.utils import platform
        if platform != "android":
            self.show_notice("A sincronização está disponível somente no aplicativo Android.")
            return
        if self._syncing:
            return
        self._syncing = True
        self._show_progress("Sincronizando…")
        token = self.token_store.get_access_token() if self.token_store else None
        if not token:
            # Sem token em memória (app recém-aberto ou expirado): pede ao Google
            # (silencioso se a permissão já foi concedida) e só então sincroniza.
            self._sync_after_auth = True
            self.connect_gmail()
            return
        self._start_sync()

    def _start_sync(self):
        threading.Thread(target=self._sync_worker, daemon=True).start()

    def _sync_worker(self):
        from src.mail.gmail_api import AuthError, GmailClient, GmailError
        from src.services.sync_service import SyncService
        try:
            client = GmailClient(self.token_store.get_access_token())
            service = SyncService(self.db, client, progress=self._post_progress)
            result = service.run()
        except AuthError:
            Clock.schedule_once(lambda _dt: self._sync_auth_failed(), 0)
        except GmailError as exc:
            Clock.schedule_once(lambda _dt, m=str(exc): self._sync_failed(m), 0)
        except Exception:
            log.exception("Falha inesperada na sincronização")
            Clock.schedule_once(lambda _dt: self._sync_failed(
                "Não foi possível sincronizar. Tente novamente."), 0)
        else:
            Clock.schedule_once(lambda _dt: self._sync_done(result), 0)

    def _sync_auth_failed(self):
        """Token expirou (~1 h): pede outro ao Google uma única vez e repete."""
        self.token_store.clear()
        if self._auth_retried:
            self._auth_retried = False
            self.gmail_authorized = False
            self._sync_failed("Sua conexão com o Gmail expirou. Conecte a conta novamente.")
            return
        self._auth_retried = True
        self._sync_after_auth = True
        self.connect_gmail()

    def _sync_done(self, result):
        self._auth_retried = False
        self.account_email = result.account_email
        self._finish_sync_ui()
        self._refresh_current_screen()
        self.show_notice(f"Sincronizado: {result.added} nova(s) mensagem(ns)"
                         + (f", {result.deleted} removida(s)." if result.deleted else "."))

    def _sync_failed(self, message):
        self._auth_retried = False
        self._finish_sync_ui()
        self._refresh_current_screen()
        self.show_notice(message)

    def _post_progress(self, text):  # chamado da thread
        Clock.schedule_once(lambda _dt: self._set_progress(text), 0)

    def _show_progress(self, text):
        self._progress_label = Label(text=text, halign="center")
        self._progress_popup = Popup(title="Sincronizando", content=self._progress_label,
                                     size_hint=(.82, None), height=dp(150), auto_dismiss=False)
        self._progress_popup.open()

    def _set_progress(self, text):
        if self._progress_label is not None:
            self._progress_label.text = text

    def _finish_sync_ui(self):
        self._syncing = False
        if self._progress_popup is not None:
            self._progress_popup.dismiss()
            self._progress_popup = None
            self._progress_label = None

    def _refresh_current_screen(self):
        screen = self.sm.current_screen
        if self.sm.current != "message" and hasattr(screen, "on_pre_enter"):
            screen.on_pre_enter()

    # ------------------------------------------------------------ diálogos
    def show_notice(self, message):
        label = Label(text=message, halign="center", valign="middle")
        label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        Popup(title=settings.APP_NAME, content=label, size_hint=(.86, None),
              height=dp(230), auto_dismiss=True).open()

    def confirm(self, message, on_confirm, confirm_text="Confirmar"):
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
        label = Label(text=message, halign="center")
        label.bind(size=lambda inst, size: setattr(inst, "text_size", (size[0], None)))
        content.add_widget(label)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        popup = Popup(title=settings.APP_NAME, content=content, size_hint=(.86, None),
                      height=dp(210), auto_dismiss=False)
        cancel = AppButton(text="Cancelar", on_release=lambda *_: popup.dismiss())
        ok = AppButton(text=confirm_text, primary=True,
                       on_release=lambda *_: (popup.dismiss(), on_confirm()))
        row.add_widget(cancel)
        row.add_widget(ok)
        content.add_widget(row)
        popup.open()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    EmailManagerApp().run()
