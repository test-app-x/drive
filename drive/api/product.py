import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import escape_html
from frappe.utils import split_emails, validate_email_address
from .google import google_oauth_flow


CORPORATE_DOMAINS = ["gmail.com", "icloud.com", "frappemail.com"]


@frappe.whitelist()
def get_domain_teams(domain):
    return frappe.db.get_all("Drive Team", {"team_domain": ["like", "%" + domain]}, pluck="name")


@frappe.whitelist()
def create_personal_team(user):
    team = frappe.get_doc(
        {
            "doctype": "Drive Team",
            "title": "Your Drive",
        },
    ).insert(ignore_permissions=True)
    team.append("users", {"user": user.email, "is_admin": 1})
    team.save()
    team = team.name


@frappe.whitelist()
def request_invite(team, email=frappe.session.user):
    invite = frappe.new_doc("Drive User Invitation")
    invite.email = email
    invite.team = team
    invite.status = "Proposed"
    invite.insert(ignore_permissions=True)
    frappe.db.commit()


@frappe.whitelist()
def get_invites(email):
    invites = frappe.db.get_list(
        "Drive User Invitation",
        fields=["creation", "status", "team", "name"],
        filters={"email": email, "status": ("in", ("Proposed", "Pending"))},
    )
    for i in invites:
        i["team_name"] = frappe.db.get_value("Drive Team", i["team"], "title")
    return invites


@frappe.whitelist()
def get_team_invites(team):
    print(team)
    invites = frappe.db.get_list(
        "Drive User Invitation",
        fields=["creation", "status", "email", "name"],
        filters={"team": team, "status": ("in", ("Proposed", "Pending"))},
    )
    for i in invites:
        i["user_name"] = frappe.db.get_value("User", i["email"], "full_name")
    return invites


@frappe.whitelist(allow_guest=True)
def signup(account_request, first_name, last_name=None, team=None, referrer=None):
    account_request = frappe.get_doc("Account Request", account_request)
    if not account_request.login_count:
        frappe.throw("Email not verified")

    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": account_request.email,
            "first_name": escape_html(first_name),
            "last_name": escape_html(last_name),
            "enabled": 1,
            "user_type": "Website User",
        }
    )
    user.flags.ignore_permissions = True
    user.flags.ignore_password_policy = True
    try:
        user.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        frappe.throw("User already exists")
    account_request.signed_up = 1

    team = None
    if account_request.invite:
        invite = frappe.get_doc("Drive User Invitation", account_request.invite)
        invite.status = "Accepted"
        invite.save(ignore_permissions=True)
        # Add to that team
        team = frappe.get_doc("Drive Team", invite.team)
        team.append("users", {"user": account_request.email})
        team.save(ignore_permissions=True)
        team = invite.team

    account_request.save(ignore_permissions=True)
    frappe.local.login_manager.login_as(user.email)

    # Check invites for this user
    if not team:
        # Create team for this user
        domain = user.email.split("@")[-1]
        if domain in CORPORATE_DOMAINS:
            team = create_personal_team()
        else:
            return get_domain_teams(domain)

    return {"location": "/drive/t/" + team}


@frappe.whitelist(allow_guest=True)
def oauth_providers():
    from frappe.utils.html_utils import get_icon_html
    from frappe.utils.oauth import get_oauth2_authorize_url, get_oauth_keys
    from frappe.utils.password import get_decrypted_password

    out = []
    providers = frappe.get_all(
        "Social Login Key",
        filters={"enable_social_login": 1},
        fields=["name", "client_id", "base_url", "provider_name", "icon"],
        order_by="name",
    )

    for provider in providers:
        client_secret = get_decrypted_password("Social Login Key", provider.name, "client_secret")
        if not client_secret:
            continue

        icon = None
        if provider.icon:
            if provider.provider_name == "Custom":
                icon = get_icon_html(provider.icon, small=True)
            else:
                icon = f"<img src='{provider.icon}' alt={provider.provider_name}>"

        if provider.client_id and provider.base_url and get_oauth_keys(provider.name):
            out.append(
                {
                    "name": provider.name,
                    "provider_name": provider.provider_name,
                    "auth_url": get_oauth2_authorize_url(provider.name, "/g"),
                    "icon": icon,
                }
            )
    return out


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=60)
def send_otp(email):
    is_login = frappe.db.exists(
        "Account Request",
        {
            "email": email,
            "signed_up": 1,
        },
    )
    if not is_login:
        account_request = frappe.get_doc(
            {
                "doctype": "Account Request",
                "email": email,
            }
        ).insert(ignore_permissions=True)
        return account_request.name
    else:
        req = frappe.get_doc("Account Request", is_login, ignore_permissions=True)
        req.set_otp()
        req.send_otp()
        return is_login


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=60)
def verify_otp(account_request, otp):
    req = frappe.get_doc("Account Request", account_request)
    if req.otp != otp:
        frappe.throw("Invalid OTP")
    req.login_count += 1
    req.save(ignore_permissions=True)
    if req.signed_up:
        frappe.local.login_manager.login_as(req.email)
        return {"location": "/drive"}
    req.signed_up = 1
    req.save(ignore_permissions=True)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=60)
def resend_otp(email):
    account_request = frappe.db.get_value("Account Request", {"email": email}, "name")
    if not account_request:
        frappe.throw("OTP was never requested.")

    account_request = frappe.get_doc("Account Request", account_request)

    # if last OTP was sent less than 30 seconds ago, throw an error
    if (
        account_request.otp_generated_at
        and (frappe.utils.now_datetime() - account_request.otp_generated_at).seconds < 30
    ):
        frappe.throw("Please wait for 30 seconds before requesting a new OTP")

    account_request.reset_otp()
    account_request.send_login_mail()


@frappe.whitelist()
def invite_users(team, emails):
    if not emails:
        return

    email_string = validate_email_address(emails, throw=False)
    email_list = split_emails(email_string)
    if not email_list:
        return

    existing_invites = frappe.db.get_list(
        "Drive User Invitation",
        filters={"email": ["in", email_list], "team": team, "status": "Pending"},
        pluck="email",
    )

    new_invites = list(set(email_list) - set(existing_invites))
    for email in new_invites:
        invite = frappe.new_doc("Drive User Invitation")
        invite.email = email
        invite.team = team
        invite.status = "Pending"
        invite.insert()


@frappe.whitelist()
def set_role(team, user_id, role):
    if not is_admin(team):
        frappe.throw("You don't have the permissions for this action.")
    drive_team = {k.user: k for k in frappe.get_doc("Drive Team", team).users}
    drive_team[user_id].is_admin = role
    drive_team[user_id].save()


@frappe.whitelist()
def is_admin(team):
    drive_team = {k.user: k for k in frappe.get_doc("Drive Team", team).users}
    return drive_team[frappe.session.user].is_admin


@frappe.whitelist()
def remove_user(team, user_id):
    drive_team = {k.user: k for k in frappe.get_doc("Drive Team", team).users}
    if frappe.session.user not in drive_team:
        frappe.throw("User doesn't belong to team")
    frappe.delete_doc("Drive Team Member", drive_team[user_id].name)


@frappe.whitelist()
def get_all_users(team):
    team_users = {k.user: k.is_admin for k in frappe.get_doc("Drive Team", team).users}
    users = frappe.get_all(
        doctype="User",
        filters=[
            ["name", "in", list(team_users.keys())],
        ],
        fields=[
            "name",
            "email",
            "full_name",
            "user_image",
        ],
    )
    for u in users:
        u["role"] = "admin" if team_users[u["name"]] else "user"
    return users


@frappe.whitelist(allow_guest=True)
def accept_invite(key, redirect=True):
    try:
        invitation = frappe.get_doc("Drive User Invitation", key)
    except:
        frappe.throw("Invalid or expired key")

    return invitation.accept(redirect)


@frappe.whitelist()
def reject_invite(key):
    try:
        invitation = frappe.get_doc("Drive User Invitation", key)
    except:
        frappe.throw("Invalid or expired key")

    invitation.status = "Expired"
    invitation.save(ignore_permissions=True)
