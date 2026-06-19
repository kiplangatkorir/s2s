from pipeline.session import Session


def test_session_tracks_turns_and_trims_history():
    session = Session("demo", max_turns=2)

    session.add_user_turn("hello")
    session.add_assistant_turn("hi there")
    session.add_user_turn("how are you")

    assert len(session.turns) == 2
    assert session.turns[0].text == "hi there"
    assert session.turns[1].text == "how are you"
