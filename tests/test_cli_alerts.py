"""Console alerts survive clearing and are displayed once on the next frame."""

import pytest

from rpg_cli import Button, ConsoleAdapter, Session
from cli_static_screen import StaticScreen


def test_queued_alerts_follow_clear_in_fifo_order_and_are_drained():
    events = []
    screen = StaticScreen('Screen')
    screen.buttons = (Button('again', 'Again', lambda: screen),
                      Button('exit', 'Exit', lambda: None))
    answers = iter(['1', '2'])
    adapter = ConsoleAdapter(Session(screen),
                             read=lambda prompt: next(answers),
                             write=events.append,
                             new_screen=lambda: events.append('CLEAR'))
    assert adapter.alert('First') is None
    adapter.alert('Second')
    assert events == []

    adapter.run()

    assert events == ['CLEAR', 'First', 'Second', 'Screen', '[1] Again',
                      '[2] Exit', 'CLEAR', 'Screen', '[1] Again', '[2] Exit']


def test_alert_queued_during_read_is_displayed_on_the_next_frame():
    events = []
    screen = StaticScreen('Screen')
    screen.buttons = (Button('again', 'Again', lambda: screen),)
    answers = iter(['1', None])

    def read(prompt):
        answer = next(answers)
        if answer is None:
            raise EOFError
        adapter.alert('Read alert')
        events.append('READ')
        return answer

    adapter = ConsoleAdapter(Session(screen), read=read, write=events.append,
                             new_screen=lambda: events.append('CLEAR'))
    adapter.run()

    assert events == ['CLEAR', 'Screen', '[1] Again', 'READ', 'CLEAR',
                      'Read alert', 'Screen', '[1] Again', 'Выход.']


def test_alert_queued_while_flushing_waits_for_the_next_frame():
    events = []
    screen = StaticScreen('Screen')
    screen.buttons = (Button('again', 'Again', lambda: screen),
                      Button('exit', 'Exit', lambda: None))
    answers = iter(['1', '2'])

    def write(message):
        events.append(message)
        if message == 'First':
            adapter.alert('Deferred')

    adapter = ConsoleAdapter(Session(screen),
                             read=lambda prompt: next(answers), write=write,
                             new_screen=lambda: events.append('CLEAR'))
    adapter.alert('First')
    adapter.alert('Second')
    adapter.run()

    assert events == ['CLEAR', 'First', 'Second', 'Screen', '[1] Again',
                      '[2] Exit', 'CLEAR', 'Deferred', 'Screen',
                      '[1] Again', '[2] Exit']


@pytest.mark.parametrize('choice', ['0', '-1', '2', 'not a number'])
def test_invalid_choice_is_alerted_after_the_next_clear(choice):
    events = []
    session = Session(StaticScreen('Screen', (Button('exit', 'Exit', lambda: None),)))
    answers = iter([choice, '1'])
    adapter = ConsoleAdapter(session, read=lambda prompt: next(answers),
                             write=events.append,
                             new_screen=lambda: events.append('CLEAR'))
    adapter.run()

    assert events == ['CLEAR', 'Screen', '[1] Exit', 'CLEAR',
                      'Неверный выбор.', 'Screen', '[1] Exit']


@pytest.mark.parametrize('interrupt', [EOFError, KeyboardInterrupt])
def test_interrupt_closes_session_and_prints_exit_without_another_clear(interrupt):
    events = []
    session = Session(StaticScreen('Screen'), on_close=lambda: events.append('CLOSE'))

    def read(prompt):
        raise interrupt

    adapter = ConsoleAdapter(session, read=read, write=events.append,
                             new_screen=lambda: events.append('CLEAR'))
    adapter.alert('Notice')
    adapter.run()

    assert events == ['CLEAR', 'Notice', 'Screen', 'CLOSE', 'Выход.']
    assert session.view() is None
