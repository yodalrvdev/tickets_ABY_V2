
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from .models import db, User, Status, Ticket
from .seed_excel import import_from_excel
from . import db as _db

main_bp = Blueprint('main', __name__)

@main_bp.route("/")
@login_required
def dashboard():
    total = Ticket.query.count()
    by_status = db.session.query(Status.label, func.count(Ticket.id)).join(Ticket, isouter=True).group_by(Status.id).order_by(Status.order_index).all()
    by_eval = db.session.query(Ticket.evaluation, func.count(Ticket.id)).group_by(Ticket.evaluation).all()
    avg_age = db.session.query(func.avg(func.julianday(func.coalesce(Ticket.closed_at, func.current_timestamp())) - func.julianday(Ticket.created_at))).scalar()
    return render_template("dashboard.html", total=total, by_status=by_status, by_eval=by_eval, avg_age=round(avg_age or 0, 1))

@main_bp.route("/tickets")
@login_required
def tickets_list():
    q = Ticket.query
    status = request.args.get("status")
    person = request.args.get("person")
    who = request.args.get("who")
    year = request.args.get("year")
    if status:
        st = Status.query.filter_by(label=status).first()
        if st: q = q.filter(Ticket.status_id==st.id)
    if year:
        q = q.filter(Ticket.year==int(year))
    if person and who in ("sent","received"):
        user = User.query.filter_by(name=person).first()
        if user:
            q = q.filter(Ticket.sender_id==user.id) if who=="sent" else q = q.filter(Ticket.receiver_id==user.id)
    tickets = q.order_by(Ticket.created_at.desc()).all()
    statuses = Status.query.order_by(Status.order_index).all()
    users = User.query.order_by(User.name).all()
    years = sorted({t.year for t in Ticket.query.with_entities(Ticket.year).all()}, reverse=True)
    return render_template("tickets.html", tickets=tickets, statuses=statuses, users=users, years=years)

@main_bp.route("/tickets/new", methods=["GET","POST"])
@login_required
def ticket_new():
    statuses = Status.query.order_by(Status.order_index).all()
    users = User.query.order_by(User.name).all()
    if request.method == "POST":
        year = int(request.form.get("year"))
        status_id = int(request.form.get("status_id"))
        sender_id = int(request.form.get("sender_id"))
        receiver_id = int(request.form.get("receiver_id"))
        subject = request.form.get("subject","").strip()
        created_at = request.form.get("created_at") or None
        created_at = datetime.fromisoformat(created_at) if created_at else datetime.utcnow()
        closed_at = request.form.get("closed_at") or None
        closed_at = datetime.fromisoformat(closed_at) if closed_at else None
        evaluation = request.form.get("evaluation") or None
        revenue = request.form.get("revenue") or None
        revenue = float(revenue) if revenue not in (None, "", "None") else None
        comment = request.form.get("comment") or None

        t = Ticket(year=year, status_id=status_id, sender_id=sender_id, receiver_id=receiver_id,
                   subject=subject, created_at=created_at, closed_at=closed_at,
                   evaluation=evaluation, revenue=revenue, comment=comment)
        db.session.add(t)
        db.session.commit()
        flash("Ticket créé.", "success")
        return redirect(url_for("main.tickets_list"))
    return render_template("ticket_form.html", action="Créer", statuses=statuses, users=users)

@main_bp.route("/tickets/<int:ticket_id>/edit", methods=["GET","POST"])
@login_required
def ticket_edit(ticket_id):
    t = Ticket.query.get_or_404(ticket_id)
    statuses = Status.query.order_by(Status.order_index).all()
    users = User.query.order_by(User.name).all()
    if request.method == "POST":
        t.year = int(request.form.get("year"))
        t.status_id = int(request.form.get("status_id"))
        t.sender_id = int(request.form.get("sender_id"))
        t.receiver_id = int(request.form.get("receiver_id"))
        t.subject = request.form.get("subject","").strip()
        created_at = request.form.get("created_at") or None
        t.created_at = datetime.fromisoformat(created_at) if created_at else t.created_at
        closed_at = request.form.get("closed_at") or None
        t.closed_at = datetime.fromisoformat(closed_at) if closed_at else None
        t.evaluation = request.form.get("evaluation") or None
        revenue = request.form.get("revenue") or None
        t.revenue = float(revenue) if revenue not in (None, "", "None") else None
        t.comment = request.form.get("comment") or None
        db.session.commit()
        flash("Ticket mis à jour.", "success")
        return redirect(url_for("main.tickets_list"))
    return render_template("ticket_form.html", action="Mettre à jour", ticket=t, statuses=statuses, users=users)

@main_bp.route("/tickets/<int:ticket_id>/delete", methods=["POST"])
@login_required
def ticket_delete(ticket_id):
    t = Ticket.query.get_or_404(ticket_id)
    db.session.delete(t)
    db.session.commit()
    flash("Ticket supprimé.", "success")
    return redirect(url_for("main.tickets_list"))

@main_bp.route("/parametres", methods=["GET","POST"])
@login_required
def settings():
    statuses = Status.query.order_by(Status.order_index).all()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_status":
            label = request.form.get("label","").strip()
            if label and not Status.query.filter_by(label=label).first():
                order = (db.session.query(func.max(Status.order_index)).scalar() or 0) + 1
                db.session.add(Status(label=label, order_index=order))
                db.session.commit()
        elif action == "delete_status":
            sid = int(request.form.get("status_id"))
            st = Status.query.get(sid)
            if st:
                db.session.delete(st)
                db.session.commit()
        flash("Paramètres mis à jour.", "success")
        return redirect(url_for("main.settings"))
    return render_template("settings.html", statuses=statuses)

@main_bp.route("/admin/reimport", methods=["POST"])
@login_required
def admin_reimport():
    if not current_user.is_admin:
        flash("Accès réservé à l'administrateur.", "danger")
        return redirect(url_for("main.settings"))
    mode = (request.form.get("mode") or "reset").lower()
    if mode == "reset":
        _db.drop_all()
        _db.create_all()
        import_from_excel()
        flash("Réimport effectué (remise à zéro de la base + import Excel).", "success")
    else:
        before = Ticket.query.count()
        import_from_excel()
        after = Ticket.query.count()
        flash(f"Réimport incrémental terminé (+{after - before} tickets potentiels).", "success")
    return redirect(url_for("main.settings"))

@main_bp.route("/api/stats")
@login_required
def api_stats():
    sent = db.session.query(User.name, func.count(Ticket.id)).join(Ticket, Ticket.sender_id==User.id, isouter=True).group_by(User.id).order_by(User.name).all()
    recv = db.session.query(User.name, func.count(Ticket.id)).join(Ticket, Ticket.receiver_id==User.id, isouter=True).group_by(User.id).order_by(User.name).all()
    by_status = db.session.query(Status.label, func.count(Ticket.id)).join(Ticket, isouter=True).group_by(Status.id).order_by(Status.order_index).all()
    by_eval = db.session.query(Ticket.evaluation, func.count(Ticket.id)).group_by(Ticket.evaluation).all()
    return jsonify({
        "sent": [{"label": n, "value": c} for n,c in sent],
        "received": [{"label": n, "value": c} for n,c in recv],
        "status": [{"label": s, "value": c} for s,c in by_status],
        "evaluation": [{"label": e or "Non renseigné", "value": c} for e,c in by_eval],
    })
