"""Elementos compartilhados entre telas."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from src.ui.components import AppLabel
from src.config import settings


def app_header(show_refresh=True):
    """Barra superior: logo + nome do app à esquerda, ações à direita."""
    from kivy.app import App
    from kivy.uix.widget import Widget
    from src.ui.components import IconButton
    app = App.get_running_app()
    bar = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
    from kivy.uix.image import Image
    logo = Image(source="assets/images/logo.png", size_hint=(None, None),
                 size=(dp(48), dp(48)), fit_mode="contain", pos_hint={"center_y": .5})
    bar.add_widget(logo)
    bar.add_widget(AppLabel(text=settings.APP_NAME, bold=True, font_size="18sp",
                            size_hint_x=None, width=dp(230)))
    bar.add_widget(Widget())
    if show_refresh:
        refresh = IconButton("refresh", size=18, size_hint_x=None, width=dp(36))
        refresh.bind(on_release=lambda *_: app.sync())
        bar.add_widget(refresh)
    return bar


def page_shell(title, subtitle=None, big=False, show_refresh=True):
    root = BoxLayout(orientation="vertical", padding=[dp(16), dp(12), dp(16), 0], spacing=dp(10))
    root.add_widget(app_header(show_refresh))
    heading = BoxLayout(orientation="vertical", size_hint_y=None,
                        height=dp(60 if big else 52), spacing=dp(2))
    heading.add_widget(AppLabel(text=title, font_size="26sp" if big else "20sp", bold=True))
    if subtitle:
        heading.add_widget(AppLabel(text=subtitle, color=settings.COLORS["text_secondary"],
                                    font_size="11sp", size_hint_y=None, height=dp(16)))
    root.add_widget(heading)
    return root


def fill_list(container, emails, on_press, first=8, chunk=4):
    """Desenha os primeiros cartões na hora e o resto aos poucos (sem travar a navegação)."""
    from kivy.clock import Clock
    from src.ui.components import EmailItem
    old = getattr(container, "_fill_event", None)
    if old is not None:
        old.cancel()
    for email in emails[:first]:
        container.add_widget(EmailItem(email, on_press=on_press))
    rest = list(emails[first:])
    if not rest:
        return

    def step(_dt):
        for email in rest[:chunk]:
            container.add_widget(EmailItem(email, on_press=on_press))
        del rest[:chunk]
        if not rest:
            container._fill_event.cancel()

    container._fill_event = Clock.schedule_interval(step, 0)


def bottom_nav(current, callback):
    """Navegação inferior só com ícones, separada por uma linha fina."""
    from kivy.graphics import Color, Rectangle
    from src.ui.components import IconButton, rgba
    bar = BoxLayout(size_hint_y=None, height=dp(54))
    with bar.canvas.before:
        Color(*rgba(settings.COLORS["border"]))
        line = Rectangle(pos=bar.pos, size=(bar.width, 1))
    bar.bind(pos=lambda w, p: setattr(line, "pos", (p[0], p[1] + w.height - 1)),
             size=lambda w, s: (setattr(line, "size", (s[0], 1)),
                                setattr(line, "pos", (w.x, w.y + s[1] - 1))))
    for name, icon in [("home", "home"), ("categories", "folder"),
                       ("search", "search"), ("settings", "settings")]:
        active = name == current
        btn = IconButton(icon, size=19,
                         color=settings.COLORS["primary"] if active else settings.COLORS["text_secondary"])
        btn.bind(on_release=lambda _btn, route=name: callback(route))
        bar.add_widget(btn)
    return bar


def add_bottom(root, current):
    from kivy.app import App
    root.add_widget(bottom_nav(current, App.get_running_app().navigate))
