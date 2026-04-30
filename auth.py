"""Modulo di autenticazione per l'applicazione.

Ruoli:
  - admin : accesso completo a tutte le pagine
  - user  : accesso alla sola pagina Risorse per aggiornare le proprie
            competenze e livelli di expertise
"""

import hashlib

import streamlit as st


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _get_passwords() -> tuple[str, str]:
    """Restituisce (hash_admin, hash_user) dai secrets."""
    admin_pw = st.secrets.get("auth", {}).get("admin_password", "")
    user_pw = st.secrets.get("auth", {}).get("user_password", "")
    return admin_pw, user_pw


def get_role() -> str | None:
    """Restituisce il ruolo corrente dalla session state, o None se non loggato."""
    return st.session_state.get("auth_role")


def show_logout_button() -> None:
    """Mostra il pulsante di logout nella sidebar."""
    role = get_role()
    if role:
        with st.sidebar:
            st.divider()
            label = "Admin" if role == "admin" else st.session_state.get("auth_user_name", "Utente")
            st.caption(f"Sessione attiva: **{label}**")
            if st.button("🚪 Logout", key="_logout_btn"):
                for key in ("auth_role", "auth_user_id", "auth_user_name"):
                    st.session_state.pop(key, None)
                st.rerun()


def _show_login_form() -> None:
    """Mostra il form di login e blocca l'esecuzione se non autenticato."""
    st.markdown("## 🔐 Accesso richiesto")
    st.markdown(
        "Inserisci la password di **admin** per accedere a tutte le funzionalità, "
        "oppure la password **utente** per aggiornare le tue competenze."
    )

    admin_pw, user_pw = _get_passwords()

    with st.form("login_form"):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Accedi")

    if submitted:
        if admin_pw and password == admin_pw:
            st.session_state["auth_role"] = "admin"
            st.rerun()
        elif user_pw and password == user_pw:
            st.session_state["auth_role"] = "user"
            st.rerun()
        else:
            st.error("Password non valida.")

    st.stop()


def require_admin() -> None:
    """Blocca l'accesso se il ruolo non è admin. Mostra il login se non autenticato."""
    role = get_role()
    if role == "admin":
        show_logout_button()
        return
    if role == "user":
        st.warning("Questa pagina è riservata agli amministratori.")
        show_logout_button()
        st.stop()
    _show_login_form()


def require_any_auth() -> str:
    """Richiede autenticazione (qualsiasi ruolo). Restituisce il ruolo corrente."""
    role = get_role()
    if role in ("admin", "user"):
        show_logout_button()
        return role
    _show_login_form()
    return ""  # unreachable, _show_login_form calls st.stop()
