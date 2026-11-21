"""Componentes reutilizáveis da interface do Email Manager."""
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse

from src.config import settings


def rgba(value):
    return get_color_from_hex(value)


class Surface(BoxLayout):
    """Container com fundo arredondado e borda sutil."""
    def __init__(self, color=None, radius=dp(12), border=True, **kwargs):
        super().__init__(**kwargs)
        self._radius = radius
        with self.canvas.before:
            Color(*rgba(color or settings.COLORS["surface"]))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            if border:
                Color(*rgba(settings.COLORS["border"]))
                self._line = Line(rounded_rectangle=(*self.pos, *self.size, radius), width=1)
        self._border = border
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        if self._border:
            self._line.rounded_rectangle = (*self.pos, *self.size, self._radius)


class AppLabel(Label):
    def __init__(self, color=None, font_size="14sp", bold=False, **kwargs):
        kwargs.setdefault("halign", "left")
        kwargs.setdefault("valign", "middle")
        super().__init__(
            color=rgba(color or settings.COLORS["text"]),
            font_size=sp(float(str(font_size).replace("sp", ""))),
            bold=bold,
            **kwargs
        )
        self.bind(size=self._sync_text)
        self._sync_text()

    def _sync_text(self, *_):
        self.text_size = (self.width, None)


class Icon(Label):
    """Ícone da fonte Lucide."""
    def __init__(self, name, color=None, size=18, **kwargs):
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        super().__init__(text=settings.ICONS[name], font_name=settings.ICON_FONT,
                         font_size=sp(size), color=rgba(color or settings.COLORS["text_secondary"]),
                         **kwargs)
        self.bind(size=lambda inst, s: setattr(inst, "text_size", s))


class IconButton(ButtonBehavior, Icon):
    def __init__(self, name, **kwargs):
        # Passa pelo ButtonBehavior (registra on_press/on_release) até chegar ao Icon.
        super().__init__(name=name, **kwargs)


class AppButton(Button):
    def __init__(self, primary=False, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("color", rgba(settings.COLORS["text"]))
        kwargs.setdefault("font_size", sp(14))
        super().__init__(**kwargs)
        color = settings.COLORS["primary"] if primary else settings.COLORS["surface_alt"]
        with self.canvas.before:
            self._button_color = Color(*rgba(color))
            self._button_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *_):
        self._button_rect.pos = self.pos
        self._button_rect.size = self.size


class SearchField(TextInput):
    def __init__(self, hint="Pesquisar e-mails...", **kwargs):
        super().__init__(
            hint_text=hint,
            multiline=False,
            padding=[dp(14), dp(13)],
            size_hint_y=None,
            height=dp(48),
            background_normal="",
            background_active="",
            background_color=rgba(settings.COLORS["surface_alt"]),
            foreground_color=rgba(settings.COLORS["text"]),
            hint_text_color=rgba(settings.COLORS["text_secondary"]),
            cursor_color=rgba(settings.COLORS["primary"]),
            font_size=sp(14),
            **kwargs
        )


class CategoryPill(Label):
    """Etiqueta pequena: fundo translúcido e texto na cor da categoria."""
    def __init__(self, category="Outros", **kwargs):
        color = settings.CATEGORY_COLORS.get(category, settings.CATEGORY_COLORS["Outros"])
        super().__init__(text=category, color=rgba(color), size_hint=(None, None),
                         size=(dp(max(56, len(category) * 6.5 + 20)), dp(20)),
                         font_size=sp(10), **kwargs)
        with self.canvas.before:
            c = Color(*rgba(color))
            c.a = .2
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=self._upd, size=self._upd,
                  texture_size=lambda inst, ts: setattr(inst, "width", ts[0] + dp(18)))

    def _upd(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size


class CategoryChip(ButtonBehavior, BoxLayout):
    """Chip da home: bolinha colorida + nome da categoria."""
    def __init__(self, category, **kwargs):
        super().__init__(size_hint=(None, None), height=dp(30), padding=[dp(23), 0, dp(12), 0],
                         **kwargs)
        self._dot_color = rgba(settings.CATEGORY_COLORS.get(category, settings.CATEGORY_COLORS["Outros"]))
        label = Label(text=category, font_size=sp(11), color=rgba(settings.COLORS["text"]),
                      size_hint=(None, 1))
        label.bind(texture_size=lambda inst, ts: (setattr(inst, "width", ts[0]),
                                                  setattr(self, "width", ts[0] + dp(35))))
        self.add_widget(label)
        with self.canvas.before:
            Color(*rgba(settings.COLORS["surface_alt"]))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
            Color(*self._dot_color)
            self._dot = Ellipse(size=(dp(6), dp(6)))
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._dot.pos = (self.x + dp(11), self.y + self.height / 2 - dp(3))


class EmailItem(ButtonBehavior, Surface):
    """Cartão de e-mail clicável."""
    def __init__(self, email, on_press=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(112),
                         padding=[dp(14), dp(10)], spacing=dp(3), **kwargs)
        self.email = email
        header = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(8))
        header.add_widget(AppLabel(text=email.get("sender", "Remetente"), bold=True,
                                   font_size="15sp", shorten=True, shorten_from="right"))
        header.add_widget(AppLabel(text=email.get("date", ""), color=settings.COLORS["text_secondary"],
                                   font_size="11sp", size_hint_x=None, width=dp(78), halign="right"))
        self.add_widget(header)
        self.add_widget(AppLabel(text=email.get("subject", "(Sem assunto)"), bold=True,
                                 font_size="12sp", size_hint_y=None, height=dp(20),
                                 shorten=True, shorten_from="right"))
        text = " ".join((email.get("preview", "") or "").split())
        self.add_widget(AppLabel(text=text, color=settings.COLORS["text_secondary"],
                                 font_size="11sp", size_hint_y=None, height=dp(18),
                                 shorten=True, shorten_from="right"))
        footer = BoxLayout(size_hint_y=None, height=dp(22), padding=[0, dp(2), 0, 0])
        footer.add_widget(CategoryPill(email.get("category", "Outros")))
        footer.add_widget(Widget())
        if not email.get("is_read", True):
            footer.add_widget(AppLabel(text="Não lido", color=settings.COLORS["primary"],
                                       font_size="10sp", size_hint_x=None, width=dp(60),
                                       halign="right"))
        self.add_widget(footer)
        if on_press:
            self.bind(on_release=lambda *_: on_press(email))
