"""Test the State logic of the registration wizard."""

import reflex as rx
from myproject.myproject import State


def create_state() -> State:
    return State(_reflex_internal_init=True)


def test_initial_state():
    state = create_state()
    assert state.step == 1
    assert state.submitted is False
    assert state.error_message == ""
    assert state.name == ""
    assert state.email == ""
    assert state.address == ""
    assert state.city == ""
    assert state.password == ""
    assert state.confirm_password == ""


def test_step1_validation_empty():
    state = create_state()
    state.next_step()
    assert state.step == 1
    assert state.error_message != ""


def test_step1_validation_invalid_email():
    state = create_state()
    state.set_name("John Doe")
    state.set_email("invalid_email")
    state.next_step()
    assert state.step == 1
    assert "email" in state.error_message.lower() or "@" in state.error_message.lower()


def test_step1_validation_success():
    state = create_state()
    state.set_name("John Doe")
    state.set_email("john.doe@example.com")
    state.next_step()
    assert state.step == 2
    assert state.error_message == ""


def test_step2_validation_empty():
    state = create_state()
    state.set_name("John Doe")
    state.set_email("john.doe@example.com")
    state.next_step()
    assert state.step == 2

    state.next_step()
    assert state.step == 2
    assert state.error_message != ""


def test_step2_validation_success():
    state = create_state()
    state.set_name("John Doe")
    state.set_email("john.doe@example.com")
    state.next_step()
    
    state.set_address("123 Main St")
    state.set_city("New York")
    state.next_step()
    assert state.step == 3
    assert state.error_message == ""


def test_step3_validation_empty():
    state = create_state()
    state.step = 3
    state.submit()
    assert state.submitted is False
    assert state.error_message != ""


def test_step3_validation_mismatch():
    state = create_state()
    state.step = 3
    state.set_password("password123")
    state.set_confirm_password("different123")
    state.submit()
    assert state.submitted is False
    assert "match" in state.error_message.lower()


def test_step3_validation_success_and_clear():
    state = create_state()
    state.set_name("John Doe")
    state.set_email("john.doe@example.com")
    state.set_address("123 Main St")
    state.set_city("New York")
    state.set_password("password123")
    state.set_confirm_password("password123")
    state.step = 3

    state.submit()
    assert state.submitted is True
    assert state.error_message == ""
    # Draft fields must be cleared
    assert state.name == ""
    assert state.email == ""
    assert state.address == ""
    assert state.city == ""
    assert state.password == ""
    assert state.confirm_password == ""


def test_prev_step():
    state = create_state()
    state.step = 3
    state.prev_step()
    assert state.step == 2
    state.prev_step()
    assert state.step == 1
    state.prev_step()
    assert state.step == 1  # never outside 1..3
