"""Hack to add per-session state to Streamlit.
Usage
-----
>>> import SessionState
>>>
>>> session_state = SessionState.get(user_name='', favorite_color='black')
>>> session_state.user_name
''
>>> session_state.user_name = 'Mary'
>>> session_state.favorite_color
'black'
Since you set user_name above, next time your script runs this will be the
result:
>>> session_state = get(user_name='', favorite_color='black')
>>> session_state.user_name
'Mary'
"""

import streamlit as st

class SessionState:
    def __init__(self, session_state):
        self._state = session_state

    def __getattr__(self, name):
        if name == '_state':
            return super().__getattr__(name)
        return self._state.get(name)

    def __setattr__(self, name, value):
        if name == '_state':
            super().__setattr__(name, value)
        else:
            self._state[name] = value

def get_session():
    if not hasattr(st.session_state, '_custom_session'):
        st.session_state._custom_session = SessionState(st.session_state)
    return st.session_state._custom_session
