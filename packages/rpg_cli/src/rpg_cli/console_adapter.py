from .session import Session


class ConsoleAdapter:
    def __init__(self, session: Session, read=input, write=print):
        self.session = session
        self.read = read
        self.write = write

    def run(self) -> None:
        try:
            while (view := self.session.view()) is not None:
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
                        self.write('Неверный выбор.')
        except (EOFError, KeyboardInterrupt):
            self.session.close()
            self.write('Выход.')
