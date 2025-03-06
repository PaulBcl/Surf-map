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



#OLD report_thread - ne fonctionne plus avec l'upgrade streamlit >=1.4. https://discuss.streamlit.io/t/modulenotfounderror-no-module-named-streamlit-report-thread/20983/14
#remplacé par ci-après get_script_run_ctx

try:
    import streamlit.ReportThread as ReportThread
    from streamlit.server.Server import Server
except Exception:
    # Streamlit >= 0.65.0
    import streamlit.report_thread as ReportThread
    from streamlit.server.server import Server

"""
#a essayer plus tard quand upgrade de streamlit mais génère encore des erreurs " 'AppSession' object has no attribute 'enqueue'"
try:
    from streamlit.scriptrunner import get_script_run_ctx
except ModuleNotFoundError:
    # streamlit < 1.8
    try:
        from streamlit.script_run_context import get_script_run_ctx  # type: ignore
    except ModuleNotFoundError:
        # streamlit < 1.4
        from streamlit.report_thread import (  # type: ignore
            get_report_ctx as get_script_run_ctx,
        )
from streamlit.server.server import Server"""

import streamlit as st

class SessionState:
    def __init__(self, session_state, **kwargs):
        for key, val in kwargs.items():
            if key not in session_state:
                session_state[key] = val
        self._state = session_state

    def __getattr__(self, name):
        return self._state.get(name)

    def __setattr__(self, name, value):
        self._state[name] = value

def get_session():
    if not hasattr(st.session_state, '_custom_session'):
        st.session_state._custom_session = SessionState(st.session_state)
    return st.session_state._custom_session
