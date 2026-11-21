"""Autorização Google nativa via Google Identity Services (Android).

Não usa redirect URI, navegador controlado pelo app, client secret ou servidor.
O SDK do Google gerencia a autorização e devolve um access token de curta duração.
"""
import logging

from kivy.clock import Clock
from jnius import autoclass
from jnius import PythonJavaClass, java_method
from android import activity, mActivity

from src.config import settings
from src.services.token_store import TokenStore

log = logging.getLogger(__name__)
REQUEST_CODE = 0x4A31
PICK_CODE = 0x4A32


class _SuccessListener(PythonJavaClass):
    __javainterfaces__ = ["com/google/android/gms/tasks/OnSuccessListener"]
    __javacontext__ = "app"

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    @java_method("(Ljava/lang/Object;)V")
    def onSuccess(self, result):
        Clock.schedule_once(lambda _dt: self.callback(result), 0)


class _FailureListener(PythonJavaClass):
    __javainterfaces__ = ["com/google/android/gms/tasks/OnFailureListener"]
    __javacontext__ = "app"

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    @java_method("(Ljava/lang/Exception;)V")
    def onFailure(self, error):
        Clock.schedule_once(lambda _dt: self.callback(error), 0)


class GoogleAuth:
    """Ponte entre Kivy e AuthorizationClient do Google Play Services."""

    def __init__(self, token_store: TokenStore, on_authorized, on_error):
        self.token_store = token_store
        self.on_authorized = on_authorized
        self.on_error = on_error
        self._listeners = []  # Mantém referências Java/Python até concluir as Tasks.
        self._client = None
        self._active = False
        activity.bind(on_activity_result=self._on_activity_result)

    @staticmethod
    def _scopes():
        Scope = autoclass("com.google.android.gms.common.api.Scope")
        ArrayList = autoclass("java.util.ArrayList")
        scopes = ArrayList()
        for value in settings.GOOGLE_SCOPES:
            scopes.add(Scope(value))
        return scopes

    def _get_client(self):
        if self._client is None:
            Identity = autoclass("com.google.android.gms.auth.api.identity.Identity")
            self._client = Identity.getAuthorizationClient(mActivity)
        return self._client

    def pick_account(self):
        """Mostra o seletor de contas Google do aparelho e autoriza a conta escolhida."""
        if self._active:
            return
        self._active = True
        try:
            AccountManager = autoclass("android.accounts.AccountManager")
            intent = AccountManager.newChooseAccountIntent(
                None, None, ["com.google"], None, None, None, None)
            mActivity.startActivityForResult(intent, PICK_CODE)
        except Exception as exc:
            self._active = False
            log.exception("Não foi possível abrir o seletor de contas")
            self.on_error(self._friendly_error(exc))

    def authorize(self, email=None):
        """Solicita gmail.readonly; a UI de consentimento é gerenciada pelo Google.

        Com `email`, a autorização é feita para essa conta específica.
        """
        if self._active and email is None:
            return
        self._active = True
        try:
            AuthorizationRequest = autoclass(
                "com.google.android.gms.auth.api.identity.AuthorizationRequest"
            )
            builder = AuthorizationRequest.builder().setRequestedScopes(self._scopes())
            if email:
                Account = autoclass("android.accounts.Account")
                builder = builder.setAccount(Account(email, "com.google"))
            request = builder.build()
            task = self._get_client().authorize(request)
            success = _SuccessListener(self._handle_authorization)
            failure = _FailureListener(self._handle_error)
            self._listeners.extend([success, failure])
            task.addOnSuccessListener(success)
            task.addOnFailureListener(failure)
        except Exception as exc:
            self._active = False
            log.exception("Não foi possível iniciar a autorização Google")
            self.on_error(self._friendly_error(exc))

    def _handle_authorization(self, result):
        try:
            if result.hasResolution():
                pending_intent = result.getPendingIntent()
                mActivity.startIntentSenderForResult(
                    pending_intent.getIntentSender(), REQUEST_CODE,
                    None, 0, 0, 0
                )
                return
            self._accept_result(result)
        except Exception as exc:
            self._active = False
            log.exception("Falha ao processar autorização Google")
            self.on_error(self._friendly_error(exc))

    def _on_activity_result(self, request_code, result_code, intent):
        # Chamado na thread de UI do Android: nunca mexer em widgets Kivy daqui.
        if request_code == PICK_CODE:
            Clock.schedule_once(lambda _dt: self._process_pick_result(result_code, intent), 0)
            return
        if request_code != REQUEST_CODE:
            return
        Clock.schedule_once(lambda _dt: self._process_activity_result(result_code, intent), 0)

    def _process_pick_result(self, result_code, intent):
        try:
            Activity = autoclass("android.app.Activity")
            name = None
            if result_code == Activity.RESULT_OK and intent is not None:
                name = intent.getStringExtra("authAccount")
        except Exception:
            log.exception("Falha ao ler a conta escolhida")
            name = None
        self._active = False
        if not name:
            self.on_error("Nenhuma conta foi selecionada.")
            return
        self.authorize(str(name))

    def _process_activity_result(self, result_code, intent):
        try:
            Activity = autoclass("android.app.Activity")
            if result_code != Activity.RESULT_OK or intent is None:
                self._active = False
                self.on_error("A autorização foi cancelada ou não foi concluída.")
                return
            result = self._get_client().getAuthorizationResultFromIntent(intent)
            self._accept_result(result)
        except Exception as exc:
            self._active = False
            log.exception("O retorno da autorização Google falhou")
            self.on_error(self._friendly_error(exc))

    def _accept_result(self, result):
        token = result.getAccessToken()
        granted = list(result.getGrantedScopes() or [])
        granted_values = set()
        for item in granted:
            try:
                granted_values.add(str(item.getScope()))
            except Exception:
                granted_values.add(str(item))
        required = settings.GOOGLE_SCOPES[0]
        if not token or required not in granted_values:
            self._active = False
            self.on_error("O Google não concedeu a permissão necessária gmail.readonly.")
            return
        self.token_store.set_access_token(str(token))
        self._active = False
        self.on_authorized()

    def _handle_error(self, error):
        self._active = False
        log.error("Google authorize falhou: %s", error)
        self.on_error(self._friendly_error(error))

    @staticmethod
    def _friendly_error(error):
        message = str(error)
        if "GooglePlayServicesNotAvailable" in message or "SERVICE_MISSING" in message:
            return "O Google Play Services não está disponível ou precisa ser atualizado."
        return "Não foi possível conectar à conta Google. Verifique a conexão e tente novamente."

    def close(self):
        try:
            activity.unbind(on_activity_result=self._on_activity_result)
        except Exception:
            log.debug("Listener de activity já estava desvinculado", exc_info=True)
        self._listeners.clear()
