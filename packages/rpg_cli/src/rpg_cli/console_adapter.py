from .session import Session


class ConsoleAdapter:
    def __init__(self, session: Session, read=input, write=print, new_screen=lambda *args, **kwargs: None):
        self.session = session
        self.read = read
        self.write = write
        self.new_screen = new_screen
        self._alerts: list[str] = []

    def alert(self, message: str) -> None:
        self._alerts.append(message)

    def run(self) -> None:
        try:
            while (view := self.session.view()) is not None:
                self.new_screen()
                alerts, self._alerts = self._alerts, []
                for message in alerts:
                    self.write(message)
                self.write(view.text)
                if view.input_prompt is not None:
                    self.write('Введите значение. /back — отменить ввод; /home — домой.')
                else:
                    for index, button in enumerate(view.buttons, 1):
                        self.write(f'[{index}] {button.label}')
                raw = self.read(view.input_prompt or 'Ваш выбор: ')
                if view.input_prompt is not None:
                    self.session.submit_input(raw)
                elif raw.strip() in ('/home', '/back'):
                    self.session.select(raw.strip()[1:])
                else:
                    try:
                        index = int(raw)
                    except ValueError:
                        index = 0
                    if 1 <= index <= len(view.buttons):
                        self.session.select(view.buttons[index - 1].id)
                    else:
                        self.alert('Неверный выбор.')
        except (EOFError, KeyboardInterrupt):
            self.session.close()
            self.write('Выход.')
