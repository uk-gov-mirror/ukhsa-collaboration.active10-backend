from models import EmailPreference


def test_read_user_with_token(client, authenticated_user):
    response = client.get(
        "/v1/users",
        headers={"Authorization": f"Bearer {authenticated_user.token.token}"},
    )

    assert response.status_code == 200  # noqa: PLR2004
    data = response.json()

    assert data["first_name"] == "Default"
    assert data["id"] == authenticated_user.id


def test_read_user_without_token(client):
    response = client.get("/v1/users")
    assert response.status_code == 403  # noqa: PLR2004


def test_read_user_unauthenticated_token(client, unauthenticated_user):
    response = client.get(
        "/v1/users",
        headers={"Authorization": f"Bearer {unauthenticated_user.token.token}"},
    )
    assert response.status_code == 403  # noqa: PLR2004
    assert response.json() == {"detail": "Token is not valid"}


def test_public_unsubscribe_by_email_hash(client, authenticated_user, db_session):
    preference_name = "active10_mailing_list"

    subscribe_response = client.post(
        "/v1/users/email_preferences/subscribe",
        json={"name": preference_name},
        headers={"Authorization": f"Bearer {authenticated_user.token.token}"},
    )

    assert subscribe_response.status_code == 200  # noqa: PLR2004

    email_preference = (
        db_session.query(EmailPreference)
        .filter_by(user_id=authenticated_user.id, name=preference_name)
        .one()
    )
    assert email_preference.email_hash
    assert len(email_preference.email_hash) == 64  # noqa: PLR2004
    assert email_preference.is_active is True

    unsubscribe_response = client.post(
        "/v1/users/public/email_preferences/unsubscribe/",
        json={"email": "DEFAULT@example.com", "name": preference_name},
    )

    assert unsubscribe_response.status_code == 200  # noqa: PLR2004
    db_session.refresh(email_preference)
    assert email_preference.is_active is False


def test_public_unsubscribe_by_email_hash_does_not_reveal_unknown_email(client):
    response = client.post(
        "/v1/users/public/email_preferences/unsubscribe/",
        json={"email": "unknown@example.com", "name": "active10_mailing_list"},
    )

    assert response.status_code == 200  # noqa: PLR2004
