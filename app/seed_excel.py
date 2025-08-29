
from pathlib import Path
from datetime import datetime
import pandas as pd
from .config import Config
from .models import db, User, Status, Ticket

def _slug_email(name: str) -> str:
    import unicodedata, re
    n = unicodedata.normalize('NFKD', str(name)).encode('ascii','ignore').decode('ascii')
    slug = re.sub(r"[^a-z0-9]+", ".", n.lower().strip())
    slug = re.sub(r"\.+", ".", slug).strip(".")
    return f"{slug or 'user'}@example.com"

def _read_tickets_excel(path: Path) -> pd.DataFrame:
    df_raw = pd.read_excel(path, sheet_name="Table Tickets", header=None)
    header = df_raw.iloc[1].tolist()
    df = df_raw.iloc[2:].copy()
    df.columns = header
    df = df.loc[:, [c for c in df.columns if isinstance(c, str) and c.strip() != ""]].copy()
    rename = {
        "Année": "year",
        "Etat": "etat",
        "Date émission": "date_emission",
        "Ticket envoyé": "ticket_envoye",
        "Ticket reçu": "ticket_recu",
        "Objet": "objet",
        "Date clôture": "date_cloture",
        "Evaluation": "evaluation",
        "CA généré": "ca",
        "Commentaire": "commentaire",
    }
    df = df.rename(columns=rename)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    for col in ["date_emission","date_cloture"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    if "ca" in df.columns:
        df["ca"] = pd.to_numeric(df["ca"], errors="coerce")
    df = df.dropna(how="all")
    return df

def _extract_members(path: Path):
    pr = pd.read_excel(path, sheet_name="Paramètres", header=None)
    idx = pr[0][pr[0].astype(str).str.strip().str.lower()=="membres"].index
    names = []
    if len(idx):
        start = idx[0] + 1
        r = start
        while r < len(pr) and isinstance(pr.at[r,0], str) and pr.at[r,0].strip():
            names.append(pr.at[r,0].strip())
            r += 1
    return names

def import_from_excel():
    # Avoid double seed
    if User.query.first() or Ticket.query.first():
        return

    excel_path = Path(Config.EXCEL_PATH)
    if not excel_path.exists():
        admin = User(name="Administrateur", email=Config.ADMIN_EMAIL, is_admin=True)
        admin.set_password(Config.ADMIN_PASSWORD)
        db.session.add(admin)
        db.session.commit()
        return

    df = _read_tickets_excel(excel_path)

    admin = User(name="Administrateur", email=Config.ADMIN_EMAIL, is_admin=True)
    admin.set_password(Config.ADMIN_PASSWORD)
    db.session.add(admin)

    member_names = _extract_members(excel_path)
    if "ticket_envoye" in df.columns:
        member_names += [n for n in df["ticket_envoye"].dropna().astype(str).unique().tolist()]
    if "ticket_recu" in df.columns:
        member_names += [n for n in df["ticket_recu"].dropna().astype(str).unique().tolist()]
    seen = set(); ordered_names = []
    for n in member_names:
        if n not in seen:
            seen.add(n); ordered_names.append(n)
    users_by_name = {}
    for name in ordered_names:
        email = _slug_email(name)
        u = User(name=name, email=email, is_admin=False)
        u.set_password("changeme")
        db.session.add(u)
        users_by_name[name] = u

    default_order = ["Attente prise en charge","En cours de réalisation","Cloturé","Attente évaluation","Refusé","Sans suite"]
    found = [s for s in df["etat"].dropna().astype(str).unique().tolist() if s.strip()]
    ordered_statuses = []
    for s in default_order + found:
        if s not in ordered_statuses:
            ordered_statuses.append(s)
    statuses_by_label = {}
    for i, label in enumerate(ordered_statuses):
        st = Status(label=label, order_index=i)
        db.session.add(st)
        statuses_by_label[label] = st

    db.session.commit()

    for _, r in df.iterrows():
        try:
            year = int(r.get("year") or (r.get("date_emission").year if pd.notna(r.get("date_emission")) else datetime.utcnow().year))
        except Exception:
            year = datetime.utcnow().year
        status_label = str(r.get("etat")).strip() if pd.notna(r.get("etat")) else default_order[0]
        status = statuses_by_label.get(status_label) or list(statuses_by_label.values())[0]

        sender_name = str(r.get("ticket_envoye")).strip() if pd.notna(r.get("ticket_envoye")) else (ordered_names[0] if ordered_names else "Utilisateur")
        receiver_name = str(r.get("ticket_recu")).strip() if pd.notna(r.get("ticket_recu")) else (ordered_names[0] if ordered_names else "Utilisateur")
        sender = users_by_name.get(sender_name)
        if sender is None:
            sender = User(name=sender_name, email=_slug_email(sender_name))
            sender.set_password("changeme")
            db.session.add(sender); db.session.flush()
            users_by_name[sender_name] = sender
        receiver = users_by_name.get(receiver_name)
        if receiver is None:
            receiver = User(name=receiver_name, email=_slug_email(receiver_name))
            receiver.set_password("changeme")
            db.session.add(receiver); db.session.flush()
            users_by_name[receiver_name] = receiver

        subject = str(r.get("objet")).strip() if pd.notna(r.get("objet")) else "(Sans objet)"
        created_at = r.get("date_emission")
        closed_at = r.get("date_cloture") if pd.notna(r.get("date_cloture")) else None
        evaluation = str(r.get("evaluation")).strip() if pd.notna(r.get("evaluation")) else None
        ca = float(r.get("ca")) if pd.notna(r.get("ca")) else None
        comment = str(r.get("commentaire")).strip() if pd.notna(r.get("commentaire")) else None

        t = Ticket(year=year, status_id=status.id, sender_id=sender.id, receiver_id=receiver.id,
                   subject=subject, created_at=created_at if pd.notna(created_at) else datetime(year,1,1,12,0,0),
                   closed_at=closed_at, evaluation=evaluation, revenue=ca, comment=comment)
        db.session.add(t)

    db.session.commit()
